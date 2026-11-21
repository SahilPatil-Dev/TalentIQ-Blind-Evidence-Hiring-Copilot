"""
Automated tests. Run them with:   python manage.py test evaluations

They protect the promises the app makes:
  * identity is redacted before the AI sees anything
  * every quote must exist in the resume (the AI can't invent evidence)
  * the score is plain maths, so the same resume always gets the same score
  * identity is only revealed after the recruiter shortlists
"""
import json
from io import BytesIO, StringIO
from unittest.mock import patch
from urllib.error import URLError

from django.test import TestCase
from django.test import override_settings
from rest_framework.test import APIClient

from .models import CandidateApplication, JobRole
from .services.evaluator import calculate_score, evaluate_candidate
from .services.mistral import MistralAPIError
from .services.privacy import decrypt_pii, encrypt_pii, redact_resume


class PrivacyTests(TestCase):
    """Redaction + encryption of identity details."""

    def test_redacts_identity_and_encrypts_original_values(self):
        text = (
            "Name: Alex Example\nEmail: alex@example.test\n"
            "Phone: +1 (555) 123-4567\nExample State University\n"
            "She built a Python service."
        )
        redacted, pii = redact_resume(text)
        self.assertNotIn("Alex Example", redacted)
        self.assertNotIn("alex@example.test", redacted)
        self.assertNotIn("555", redacted)
        self.assertNotIn("Example State University", redacted)
        self.assertNotIn("She", redacted)
        self.assertEqual(pii["name"], "Alex Example")
        self.assertEqual(decrypt_pii(encrypt_pii(pii)), pii)


@override_settings(MISTRAL_API_KEY="")  # tests must never use a real key from .env
class EvaluationTests(TestCase):
    """The LangGraph flow: quotes, validation, retries and scoring."""

    def setUp(self):
        self.criteria = [
            {"name": "Python", "weight": 60, "keywords": ["Python"]},
            {"name": "PostgreSQL", "weight": 40, "keywords": ["PostgreSQL"]},
        ]

    def test_evidence_quotes_are_verbatim_and_score_is_deterministic(self):
        text = "Built a Python API. Used PostgreSQL for persistence."
        first = evaluate_candidate(text, self.criteria)
        second = evaluate_candidate(text, self.criteria)
        self.assertEqual(first["final_score"], 100)
        self.assertEqual(first["final_score"], second["final_score"])
        self.assertEqual(
            [item["quote"] for item in first["evidence_matrix"]],
            ["Built a Python API.", "Used PostgreSQL for persistence."],
        )

    def test_partial_and_missing_evidence_only_award_partial_points(self):
        evidence = [
            {"weight": 60, "status": "partial"},
            {"weight": 40, "status": "missing"},
        ]
        self.assertEqual(calculate_score(evidence), 30)

    def test_keyword_dump_is_not_accepted_as_project_evidence(self):
        result = evaluate_candidate(
            "Keywords: Python, PostgreSQL. No project experience listed.",
            self.criteria,
        )
        self.assertEqual(result["final_score"], 0)
        self.assertTrue(all(item["status"] == "missing" for item in result["evidence_matrix"]))

    @override_settings(
        MISTRAL_API_KEY="test-api-key",
        MISTRAL_MODEL="codestral-2508",
        MISTRAL_API_URL="https://api.mistral.ai/v1/chat/completions",
    )
    @patch("evaluations.services.mistral.urlopen")
    def test_codestral_extracts_quotes_but_python_calculates_score(self, mock_urlopen):
        text = "Built a Python API. Used PostgreSQL for persistence."
        response_body = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "evidence": [
                                    {
                                        "criterion": "Python",
                                        "status": "verified",
                                        "quote": "Built a Python API.",
                                    },
                                    {
                                        "criterion": "PostgreSQL",
                                        "status": "verified",
                                        "quote": "Used PostgreSQL for persistence.",
                                    },
                                ]
                            }
                        )
                    }
                }
            ]
        }
        response = BytesIO(json.dumps(response_body).encode())
        response.__enter__ = lambda: response
        response.__exit__ = lambda *args: None
        mock_urlopen.return_value = response

        result = evaluate_candidate(text, self.criteria)

        self.assertEqual(result["final_score"], 100)
        self.assertEqual(result["workflow_trace"][1], "Extracting evidence with codestral-2508")
        request = mock_urlopen.call_args.args[0]
        request_payload = json.loads(request.data)
        self.assertEqual(request_payload["model"], "codestral-2508")
        self.assertEqual(request_payload["temperature"], 0)

    @override_settings(
        MISTRAL_API_KEY="test-api-key",
        MISTRAL_MODEL="codestral-2508",
        MISTRAL_API_URL="https://api.mistral.ai/v1/chat/completions",
    )
    @patch("evaluations.services.mistral.urlopen")
    def test_invalid_model_quotes_are_retried_and_never_award_points(self, mock_urlopen):
        text = "Built a Python API. Used PostgreSQL for persistence."
        responses = [
            {
                "choices": [{"message": {"content": json.dumps({"evidence": [
                    {"criterion": "Python", "status": "verified", "quote": "Invented experience"},
                    {"criterion": "PostgreSQL", "status": "missing", "quote": ""},
                ]})}}]
            },
            {
                "choices": [{"message": {"content": json.dumps({"evidence": [
                    {"criterion": "Python", "status": "verified", "quote": "Still invented"},
                    {"criterion": "PostgreSQL", "status": "missing", "quote": ""},
                ]})}}]
            },
        ]
        context_responses = []
        for body in responses:
            response = BytesIO(json.dumps(body).encode())
            response.__enter__ = lambda response=response: response
            response.__exit__ = lambda *args: None
            context_responses.append(response)
        mock_urlopen.side_effect = context_responses

        result = evaluate_candidate(text, self.criteria)

        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertEqual(result["final_score"], 0)
        self.assertEqual(result["evidence_matrix"][0]["status"], "missing")
        self.assertEqual(result["evidence_matrix"][0]["quote"], "")
        self.assertIn("Retrying unsupported citations", result["workflow_trace"])

    @override_settings(
        MISTRAL_API_KEY="test-api-key",
        MISTRAL_MODEL="codestral-2508",
        MISTRAL_API_URL="https://api.mistral.ai/v1/chat/completions",
    )
    @patch("evaluations.services.mistral.urlopen")
    def test_valid_quote_from_retry_can_be_scored(self, mock_urlopen):
        contents = [
            {"evidence": [{"criterion": "Python", "status": "verified", "quote": "Not in the resume"}]},
            {"evidence": [{"criterion": "Python", "status": "verified", "quote": "Built a Python API."}]},
        ]
        responses = []
        for content in contents:
            response_body = {"choices": [{"message": {"content": json.dumps(content)}}]}
            response = BytesIO(json.dumps(response_body).encode())
            responses.append(response)
        mock_urlopen.side_effect = responses

        result = evaluate_candidate("Built a Python API.", [self.criteria[0]])

        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertEqual(result["final_score"], 60)
        self.assertEqual(result["evidence_matrix"][0]["quote"], "Built a Python API.")

    @override_settings(
        MISTRAL_API_KEY="test-api-key",
        MISTRAL_MODEL="codestral-2508",
        MISTRAL_API_URL="https://api.mistral.ai/v1/chat/completions",
    )
    @patch("evaluations.services.mistral.urlopen", side_effect=URLError("offline"))
    def test_configured_model_failure_is_not_silently_replaced(self, mock_urlopen):
        with self.assertRaises(MistralAPIError):
            evaluate_candidate("Built a Python API.", self.criteria)
        mock_urlopen.assert_called_once()


@override_settings(MISTRAL_API_KEY="")  # tests must never use a real key from .env
class ApplicationApiTests(TestCase):
    """The HTTP API end to end (upload -> review -> decision)."""

    def setUp(self):
        self.client = APIClient()
        self.job = JobRole.objects.create(
            title="Backend Engineer",
            rubric_criteria=[
                {"name": "Python", "weight": 100, "keywords": ["Python"]}
            ],
        )

    def test_identity_is_hidden_until_shortlisted(self):
        response = self.client.post(
            f"/api/jobs/{self.job.pk}/applications/",
            {
                "resume_text": "Name: Alex Example\nEmail: alex@example.test\nPython engineer."
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        application_id = response.data["id"]
        detail = self.client.get(f"/api/applications/{application_id}/")
        self.assertNotIn("identity", detail.data)
        decision = self.client.post(
            f"/api/applications/{application_id}/decision/",
            {"decision": "shortlist"},
            format="json",
        )
        self.assertEqual(decision.status_code, 200)
        revealed = self.client.get(f"/api/applications/{application_id}/")
        self.assertEqual(revealed.data["identity"]["name"], "Alex Example")
        self.assertEqual(revealed.data["identity"]["email"], "alex@example.test")

    def test_rejected_application_does_not_reveal_identity(self):
        response = self.client.post(
            f"/api/jobs/{self.job.pk}/applications/",
            {"resume_text": "Name: Alex Example\nPython engineer."},
            format="json",
        )
        application_id = response.data["id"]
        self.client.post(
            f"/api/applications/{application_id}/decision/",
            {"decision": "reject"},
            format="json",
        )
        detail = self.client.get(f"/api/applications/{application_id}/")
        self.assertNotIn("identity", detail.data)

    def test_invalid_rubric_weights_are_rejected(self):
        response = self.client.post(
            "/api/jobs/",
            {
                "title": "Invalid",
                "rubric_criteria": [
                    {"name": "Python", "weight": 80, "keywords": ["Python"]}
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    @override_settings(
        MISTRAL_API_KEY="test-api-key",
        MISTRAL_MODEL="codestral-2508",
        MISTRAL_API_URL="https://api.mistral.ai/v1/chat/completions",
    )
    @patch("evaluations.services.mistral.urlopen")
    def test_only_redacted_resume_is_sent_to_codestral(self, mock_urlopen):
        body = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "evidence": [
                                    {
                                        "criterion": "Python",
                                        "status": "verified",
                                        "quote": "Python engineer.",
                                    }
                                ]
                            }
                        )
                    }
                }
            ]
        }
        response = BytesIO(json.dumps(body).encode())
        mock_urlopen.return_value = response
        result = self.client.post(
            f"/api/jobs/{self.job.pk}/applications/",
            {
                "resume_text": (
                    "Name: Alex Example\nEmail: alex@example.test\n"
                    "Python engineer."
                )
            },
            format="json",
        )

        self.assertEqual(result.status_code, 201)
        request_payload = json.loads(mock_urlopen.call_args.args[0].data)
        prompt = json.loads(request_payload["messages"][1]["content"])
        self.assertNotIn("Alex Example", prompt["resume_text"])
        self.assertNotIn("alex@example.test", prompt["resume_text"])
        self.assertIn("[CANDIDATE_ID_REDACTED]", prompt["resume_text"])

    @override_settings(
        MISTRAL_API_KEY="test-api-key",
        MISTRAL_MODEL="codestral-2508",
        MISTRAL_API_URL="https://api.mistral.ai/v1/chat/completions",
    )
    @patch("evaluations.services.mistral.urlopen", side_effect=URLError("offline"))
    def test_upstream_model_error_is_reported_without_creating_application(
        self, mock_urlopen
    ):
        response = self.client.post(
            f"/api/jobs/{self.job.pk}/applications/",
            {"resume_text": "Python engineer."},
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(CandidateApplication.objects.count(), 0)
        mock_urlopen.assert_called_once()


@override_settings(MISTRAL_API_KEY="")  # tests must never use a real key from .env
class LocalMatcherTests(TestCase):
    """The keyword matcher used when no Mistral key is configured."""

    def test_keywords_match_whole_words_only(self):
        # "RAG" must not match inside "storage" or "leveraged".
        criteria = [{"name": "RAG", "weight": 100, "keywords": ["RAG"]}]
        text = "Improved storage costs. Leveraged caching."
        result = evaluate_candidate(text, criteria)
        self.assertEqual(result["final_score"], 0)

    def test_keyword_at_end_of_sentence_still_matches(self):
        criteria = [{"name": "Docker", "weight": 100, "keywords": ["Docker"]}]
        result = evaluate_candidate("Deployed services with Docker.", criteria)
        self.assertEqual(result["final_score"], 100)


@override_settings(MISTRAL_API_KEY="")  # tests must never use a real key from .env
class ApiBehaviourTests(TestCase):
    """Error handling, health check, throttling and the demo seeder."""

    def setUp(self):
        from django.core.cache import cache

        cache.clear()  # the throttle counts requests in the cache
        self.client = APIClient()
        self.job = JobRole.objects.create(
            title="Backend Engineer",
            rubric_criteria=[{"name": "Python", "weight": 100, "keywords": ["Python"]}],
        )

    def test_health_endpoint(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"status": "ok"})

    def test_unknown_role_and_application_return_404(self):
        self.assertEqual(self.client.get("/api/jobs/9999/").status_code, 404)
        self.assertEqual(self.client.get("/api/applications/9999/").status_code, 404)

    def test_empty_resume_is_rejected(self):
        response = self.client.post(
            f"/api/jobs/{self.job.pk}/applications/", {"resume_text": "  "}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_unsupported_file_type_is_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        bad_file = SimpleUploadedFile("resume.exe", b"binary")
        response = self.client.post(
            f"/api/jobs/{self.job.pk}/applications/", {"resume": bad_file}, format="multipart"
        )
        self.assertEqual(response.status_code, 400)

    def test_text_file_upload_works(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        resume = SimpleUploadedFile("resume.txt", b"Python engineer.")
        response = self.client.post(
            f"/api/jobs/{self.job.pk}/applications/", {"resume": resume}, format="multipart"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["final_score"], 100)

    def test_a_decision_can_only_be_made_once(self):
        created = self.client.post(
            f"/api/jobs/{self.job.pk}/applications/",
            {"resume_text": "Python engineer."},
            format="json",
        )
        url = f"/api/applications/{created.data['id']}/decision/"
        self.assertEqual(self.client.post(url, {"decision": "reject"}, format="json").status_code, 200)
        self.assertEqual(self.client.post(url, {"decision": "shortlist"}, format="json").status_code, 409)

    def test_invalid_decision_value_is_rejected(self):
        created = self.client.post(
            f"/api/jobs/{self.job.pk}/applications/",
            {"resume_text": "Python engineer."},
            format="json",
        )
        response = self.client.post(
            f"/api/applications/{created.data['id']}/decision/",
            {"decision": "maybe"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_uploads_are_rate_limited(self):
        from unittest.mock import patch as patch_object

        from .views import UploadThrottle

        url = f"/api/jobs/{self.job.pk}/applications/"
        with patch_object.object(UploadThrottle, "THROTTLE_RATES", {"upload": "2/hour"}):
            codes = [
                self.client.post(url, {"resume_text": "Python engineer."}, format="json").status_code
                for _ in range(3)
            ]
        self.assertEqual(codes, [201, 201, 429])

    @override_settings(MISTRAL_API_KEY="test-api-key")
    @patch("evaluations.services.mistral.urlopen")
    def test_seed_demo_is_idempotent_and_never_calls_mistral(self, mock_urlopen):
        from django.core.management import call_command

        call_command("seed_demo", stdout=StringIO())
        call_command("seed_demo", stdout=StringIO())  # twice must not duplicate anything
        self.assertEqual(JobRole.objects.filter(title="Junior AI & Backend Engineer").count(), 1)
        self.assertEqual(CandidateApplication.objects.count(), 6)
        mock_urlopen.assert_not_called()
