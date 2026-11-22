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

from .models import AuditLog, CandidateApplication, EncryptionKey, JobRole, Profile
from .services.evaluator import calculate_score, evaluate_candidate
from .services.mistral import MistralAPIError
from .services.privacy import decrypt_pii, encrypt_pii, redact_resume


PASSWORD = "Str0ng-pass-phrase!"


def make_user(role="recruiter", email=None, approved=True):
    """Create a user with a role (no login needed: tests use force_authenticate)."""
    from django.contrib.auth import get_user_model

    email = email or f"{role}@example.test"
    user = get_user_model().objects.create_user(username=email, email=email, password=PASSWORD)
    Profile.objects.create(user=user, role=role, is_approved=approved)
    return user


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


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
        self.client = client_for(make_user("recruiter"))
        self.job = JobRole.objects.create(
            title="Backend Engineer",
            rubric_criteria=[
                {"name": "Python", "weight": 100, "keywords": ["Python"]}
            ],
        )

    def test_identity_is_hidden_until_shortlisted_and_revealed_with_a_reason(self):
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
        reveal_url = f"/api/applications/{application_id}/reveal/"
        # Not shortlisted yet: no reveal.
        self.assertEqual(self.client.post(reveal_url, {"reason": "Schedule interview"}, format="json").status_code, 409)
        decision = self.client.post(
            f"/api/applications/{application_id}/decision/",
            {"decision": "shortlist", "reason": "Strong Python evidence"},
            format="json",
        )
        self.assertEqual(decision.status_code, 200)
        # Shortlisting alone does not reveal anything.
        after = self.client.get(f"/api/applications/{application_id}/")
        self.assertNotIn("identity", after.data)
        # A reveal needs a real reason...
        self.assertEqual(self.client.post(reveal_url, {"reason": "x"}, format="json").status_code, 400)
        # ...and then returns the identity.
        revealed = self.client.post(reveal_url, {"reason": "Schedule the interview"}, format="json")
        self.assertEqual(revealed.status_code, 200)
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
            {"decision": "reject", "reason": "Does not meet the rubric"},
            format="json",
        )
        detail = self.client.get(f"/api/applications/{application_id}/")
        self.assertNotIn("identity", detail.data)
        reveal = self.client.post(
            f"/api/applications/{application_id}/reveal/", {"reason": "Curious about the name"}, format="json"
        )
        self.assertEqual(reveal.status_code, 409)

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
        self.client = client_for(make_user("recruiter"))
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
        reject = {"decision": "reject", "reason": "Not enough evidence"}
        shortlist = {"decision": "shortlist", "reason": "Changed my mind"}
        self.assertEqual(self.client.post(url, reject, format="json").status_code, 200)
        self.assertEqual(self.client.post(url, shortlist, format="json").status_code, 409)

    def test_invalid_decision_value_is_rejected(self):
        created = self.client.post(
            f"/api/jobs/{self.job.pk}/applications/",
            {"resume_text": "Python engineer."},
            format="json",
        )
        response = self.client.post(
            f"/api/applications/{created.data['id']}/decision/",
            {"decision": "maybe", "reason": "Not sure"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_a_decision_needs_a_written_reason(self):
        created = self.client.post(
            f"/api/jobs/{self.job.pk}/applications/", {"resume_text": "Python engineer."}, format="json"
        )
        response = self.client.post(
            f"/api/applications/{created.data['id']}/decision/", {"decision": "reject"}, format="json"
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


# --------------------------------------------------------------------------
# Accounts, roles, audit, retention, keys, fairness, compliance
# --------------------------------------------------------------------------
@override_settings(MISTRAL_API_KEY="")
class AuthTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.client = APIClient()

    def register(self, email, password=PASSWORD):
        return self.client.post(
            "/api/auth/register/", {"email": email, "password": password, "name": "Test User"}, format="json"
        )

    def login(self, email, password=PASSWORD):
        return self.client.post("/api/auth/login/", {"email": email, "password": password}, format="json")

    def test_first_user_is_admin_and_later_users_wait_for_approval(self):
        self.assertEqual(self.register("boss@example.test").data["status"], "active")
        self.assertEqual(self.register("new@example.test").data["status"], "pending")
        self.assertEqual(self.login("new@example.test").status_code, 403)

        token = self.login("boss@example.test").data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        users = self.client.get("/api/users/").data
        pending = next(u for u in users if u["email"] == "new@example.test")
        self.assertEqual(pending["role"], "reviewer")
        approved = self.client.patch(f"/api/users/{pending['id']}/", {"is_approved": True, "role": "recruiter"}, format="json")
        self.assertEqual(approved.status_code, 200)

        self.client.credentials()
        self.assertEqual(self.login("new@example.test").status_code, 200)

    def test_requests_without_a_token_are_rejected_and_logout_ends_the_session(self):
        self.assertEqual(self.client.get("/api/jobs/").status_code, 401)
        self.register("boss@example.test")
        token = self.login("boss@example.test").data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_weak_password_is_rejected(self):
        self.assertEqual(self.register("a@example.test", "short").status_code, 400)
        self.assertEqual(self.register("b@example.test", "12345678901").status_code, 400)

    def test_account_locks_after_repeated_wrong_passwords(self):
        self.register("boss@example.test")
        for _ in range(5):
            self.assertEqual(self.login("boss@example.test", "wrong-password-1").status_code, 401)
        self.assertEqual(self.login("boss@example.test").status_code, 429)

    def test_last_administrator_cannot_be_removed(self):
        self.register("boss@example.test")
        token = self.login("boss@example.test").data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        me = self.client.get("/api/auth/me/").data
        response = self.client.patch(f"/api/users/{me['id']}/", {"role": "reviewer"}, format="json")
        self.assertEqual(response.status_code, 400)


@override_settings(MISTRAL_API_KEY="")
class RoleTests(TestCase):
    def setUp(self):
        self.job = JobRole.objects.create(
            title="Backend Engineer", rubric_criteria=[{"name": "Python", "weight": 100, "keywords": ["Python"]}]
        )
        self.recruiter = client_for(make_user("recruiter"))
        self.reviewer = client_for(make_user("reviewer"))
        self.auditor = client_for(make_user("auditor"))
        self.admin = client_for(make_user("admin"))

    def test_reviewer_is_read_only(self):
        self.assertEqual(self.reviewer.get("/api/jobs/").status_code, 200)
        new_role = {"title": "X", "rubric_criteria": [{"name": "A", "weight": 100, "keywords": []}]}
        self.assertEqual(self.reviewer.post("/api/jobs/", new_role, format="json").status_code, 403)
        upload = self.reviewer.post(f"/api/jobs/{self.job.pk}/applications/", {"resume_text": "Python"}, format="json")
        self.assertEqual(upload.status_code, 403)

    def test_auditor_cannot_see_candidates_but_can_see_governance(self):
        self.assertEqual(self.auditor.get("/api/jobs/").status_code, 403)
        self.assertEqual(self.auditor.get("/api/audit/").status_code, 200)
        self.assertEqual(self.auditor.get("/api/compliance/").status_code, 200)

    def test_only_admin_manages_users_keys_and_deletion(self):
        for client in (self.recruiter, self.reviewer, self.auditor):
            self.assertEqual(client.get("/api/users/").status_code, 403)
            self.assertEqual(client.get("/api/keys/").status_code, 403)
        self.assertEqual(self.admin.get("/api/users/").status_code, 200)
        self.assertEqual(self.admin.get("/api/keys/").status_code, 200)

        created = self.recruiter.post(
            f"/api/jobs/{self.job.pk}/applications/", {"resume_text": "Python engineer."}, format="json"
        )
        url = f"/api/applications/{created.data['id']}/"
        self.assertEqual(self.recruiter.delete(url).status_code, 403)
        self.assertEqual(self.admin.delete(url).status_code, 204)
        self.assertEqual(CandidateApplication.objects.count(), 0)

    def test_legal_hold_blocks_deletion(self):
        created = self.recruiter.post(
            f"/api/jobs/{self.job.pk}/applications/", {"resume_text": "Python engineer."}, format="json"
        )
        url = f"/api/applications/{created.data['id']}/"
        self.assertEqual(self.admin.post(url + "hold/", {"legal_hold": True, "reason": "Dispute"}, format="json").status_code, 200)
        self.assertEqual(self.admin.delete(url).status_code, 409)


@override_settings(MISTRAL_API_KEY="")
class AuditTests(TestCase):
    def setUp(self):
        self.job = JobRole.objects.create(
            title="Backend Engineer", rubric_criteria=[{"name": "Python", "weight": 100, "keywords": ["Python"]}]
        )
        self.recruiter = client_for(make_user("recruiter"))
        self.auditor = client_for(make_user("auditor"))

    def shortlist_and_reveal(self):
        created = self.recruiter.post(
            f"/api/jobs/{self.job.pk}/applications/",
            {"resume_text": "Name: Alex Example\nEmail: alex@example.test\nPython engineer."},
            format="json",
        )
        app_id = created.data["id"]
        self.recruiter.post(f"/api/applications/{app_id}/decision/",
                            {"decision": "shortlist", "reason": "Strong evidence"}, format="json")
        self.recruiter.post(f"/api/applications/{app_id}/reveal/", {"reason": "Book the interview"}, format="json")
        return app_id

    def test_reveals_are_logged_with_reason_but_never_with_the_identity(self):
        app_id = self.shortlist_and_reveal()
        entry = AuditLog.objects.get(action="identity.reveal")
        self.assertEqual(entry.target_id, str(app_id))
        self.assertEqual(entry.detail["reason"], "Book the interview")
        self.assertEqual(entry.detail["fields"], ["email", "name"])
        self.assertNotIn("Alex Example", json.dumps(entry.detail))
        self.assertNotIn("alex@example.test", json.dumps(entry.detail))

        detail = self.recruiter.get(f"/api/applications/{app_id}/")
        self.assertEqual(detail.data["reveal_history"][0]["reason"], "Book the interview")

    def test_chain_is_valid_and_tampering_is_detected(self):
        from .services.audit import verify_chain

        self.shortlist_and_reveal()
        self.assertTrue(verify_chain()["valid"])
        self.assertTrue(self.auditor.get("/api/audit/verify/").data["valid"])

        victim = AuditLog.objects.filter(action="application.shortlist").first()
        AuditLog.objects.filter(pk=victim.pk).update(detail={"reason": "edited later"})
        result = verify_chain()
        self.assertFalse(result["valid"])
        self.assertEqual(result["first_bad_id"], victim.pk)

    def test_audit_entries_cannot_be_modified_or_deleted(self):
        self.shortlist_and_reveal()
        entry = AuditLog.objects.first()
        with self.assertRaises(RuntimeError):
            entry.save()
        with self.assertRaises(RuntimeError):
            entry.delete()

    def test_audit_csv_export(self):
        self.shortlist_and_reveal()
        response = self.auditor.get("/api/audit/?format=csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("identity.reveal", response.content.decode())


@override_settings(MISTRAL_API_KEY="")
class RetentionTests(TestCase):
    def setUp(self):
        from datetime import timedelta

        from django.utils import timezone

        self.timedelta, self.now = timedelta, timezone.now()
        self.job = JobRole.objects.create(title="R", rubric_criteria=[{"name": "A", "weight": 100, "keywords": []}])
        self.admin = client_for(make_user("admin"))

    def application(self, status, days_old, hold=False):
        app = CandidateApplication.objects.create(
            job=self.job, redacted_text="x", encrypted_pii=encrypt_pii({"name": "N"}),
            status=status, legal_hold=hold,
        )
        when = self.now - self.timedelta(days=days_old)
        CandidateApplication.objects.filter(pk=app.pk).update(created_at=when, decided_at=when)
        return app

    def test_policy_deletes_only_expired_applications_and_respects_legal_hold(self):
        from .services import retention

        old_rejected = self.application("REJECTED", 40)       # limit 30 days: expired
        new_rejected = self.application("REJECTED", 5)        # kept
        old_undecided = self.application("NEEDS_REVIEW", 100)  # limit 90 days: expired
        held = self.application("REJECTED", 400, hold=True)   # expired but on hold
        old_shortlisted = self.application("SHORTLISTED", 100)  # limit 365 days: kept

        preview = retention.enforce(dry_run=True)
        self.assertEqual(sorted(preview["application_ids"]), sorted([old_rejected.pk, old_undecided.pk]))
        self.assertEqual(CandidateApplication.objects.count(), 5)  # dry run deletes nothing

        result = retention.enforce(dry_run=False)
        self.assertEqual(result["deleted"], 2)
        remaining = set(CandidateApplication.objects.values_list("pk", flat=True))
        self.assertEqual(remaining, {new_rejected.pk, held.pk, old_shortlisted.pk})
        self.assertTrue(AuditLog.objects.filter(action="retention.run").exists())

    def test_admin_can_change_policy_and_values_are_validated(self):
        self.assertEqual(self.admin.put("/api/retention/", {"rejected_days": 0}, format="json").status_code, 400)
        response = self.admin.put("/api/retention/", {"rejected_days": 14}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["rejected_days"], 14)

    def test_auditor_can_read_but_not_change_policy(self):
        auditor = client_for(make_user("auditor"))
        self.assertEqual(auditor.get("/api/retention/").status_code, 200)
        self.assertEqual(auditor.put("/api/retention/", {"rejected_days": 5}, format="json").status_code, 403)

    def test_management_command_runs(self):
        from django.core.management import call_command

        self.application("REJECTED", 40)
        call_command("enforce_retention", stdout=StringIO())
        self.assertEqual(CandidateApplication.objects.count(), 0)


class KeyManagementTests(TestCase):
    def test_new_data_is_versioned_and_rotation_keeps_old_data_readable(self):
        from .services import keys

        first = encrypt_pii({"name": "Alex"})
        self.assertTrue(first.startswith("v1:"))
        keys.rotate_data_key()
        second = encrypt_pii({"name": "Sam"})
        self.assertTrue(second.startswith("v2:"))
        self.assertEqual(decrypt_pii(first), {"name": "Alex"})
        self.assertEqual(EncryptionKey.objects.get(version=1).status, "retired")

    def test_reencrypt_moves_records_to_the_active_key_including_legacy_ones(self):
        import json as json_module

        from cryptography.fernet import Fernet
        from django.conf import settings

        from .services import keys

        job = JobRole.objects.create(title="R", rubric_criteria=[])
        legacy = Fernet(settings.PII_ENCRYPTION_KEY).encrypt(json_module.dumps({"name": "Old"}).encode()).decode()
        self.assertEqual(keys.key_version_of(legacy), 0)
        legacy_app = CandidateApplication.objects.create(job=job, redacted_text="x", encrypted_pii=legacy)
        current_app = CandidateApplication.objects.create(job=job, redacted_text="x", encrypted_pii=encrypt_pii({"name": "A"}))
        keys.rotate_data_key()

        self.assertEqual(keys.reencrypt_all(), 2)
        for app in (legacy_app, current_app):
            app.refresh_from_db()
            self.assertEqual(keys.key_version_of(app.encrypted_pii), 2)
        legacy_app.refresh_from_db()
        self.assertEqual(decrypt_pii(legacy_app.encrypted_pii), {"name": "Old"})
        self.assertEqual(keys.reencrypt_all(), 0)

    def test_master_key_can_be_rotated_without_losing_data(self):
        from cryptography.fernet import Fernet
        from django.conf import settings

        from .services import keys

        stored = encrypt_pii({"name": "Alex"})
        old_master = settings.KEY_ENCRYPTION_KEY
        new_master = Fernet.generate_key().decode()
        with override_settings(KEY_ENCRYPTION_KEY=f"{new_master},{old_master}"):
            keys.rewrap_keys()
        with override_settings(KEY_ENCRYPTION_KEY=new_master):  # old master no longer needed
            self.assertEqual(decrypt_pii(stored), {"name": "Alex"})

    def test_admin_endpoints_rotate_and_reencrypt(self):
        admin = client_for(make_user("admin"))
        encrypt_pii({"name": "x"})
        rotated = admin.post("/api/keys/rotate/")
        self.assertEqual(rotated.status_code, 201)
        self.assertEqual([k["status"] for k in rotated.data["keys"]], ["retired", "active"])
        self.assertEqual(admin.post("/api/keys/reencrypt/").status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action="key.rotate").exists())


@override_settings(MISTRAL_API_KEY="")
class FairnessTests(TestCase):
    def test_counterfactual_suite_passes_on_standard_resumes_and_reports_known_gaps(self):
        from .services import fairness

        passed, summary, details = fairness.run_counterfactual_suite()
        self.assertTrue(passed)
        self.assertEqual(summary["variants_leaking"], 0)
        self.assertEqual(summary["max_score_difference"], 0)
        self.assertEqual(summary["variants_tested"], 144)
        # Probes document what the pattern-based redaction does NOT catch.
        self.assertEqual(summary["probes_run"], 6)
        self.assertGreaterEqual(summary["probe_leaks"], 1)

    def test_four_fifths_rule(self):
        from .services import fairness

        result = fairness.four_fifths([
            {"name": "A", "applicants": 100, "selected": 50},
            {"name": "B", "applicants": 100, "selected": 30},
        ])
        self.assertTrue(result["any_flag"])
        self.assertEqual([g["impact_ratio"] for g in result["groups"]], [1.0, 0.6])
        even = fairness.four_fifths([
            {"name": "A", "applicants": 100, "selected": 20},
            {"name": "B", "applicants": 100, "selected": 19},
        ])
        self.assertFalse(even["any_flag"])
        with self.assertRaises(ValueError):
            fairness.four_fifths([{"name": "A", "applicants": 0, "selected": 0}, {"name": "B", "applicants": 5, "selected": 1}])

    def test_api_runs_are_saved_and_audited(self):
        auditor = client_for(make_user("auditor"))
        response = auditor.post("/api/fairness/runs/")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["passed"])
        self.assertEqual(len(auditor.get("/api/fairness/runs/").data), 1)
        self.assertTrue(AuditLog.objects.filter(action="fairness.run").exists())
        bad = auditor.post("/api/fairness/adverse-impact/", {"groups": "nope"}, format="json")
        self.assertEqual(bad.status_code, 400)
        recruiter = client_for(make_user("recruiter"))
        self.assertEqual(recruiter.post("/api/fairness/runs/").status_code, 403)


@override_settings(MISTRAL_API_KEY="")
class ComplianceTests(TestCase):
    def test_report_lists_checks_and_flags_open_items(self):
        admin = client_for(make_user("admin"))
        response = admin.get("/api/compliance/")
        self.assertEqual(response.status_code, 200)
        ids = {check["id"] for check in response.data["checks"]}
        self.assertTrue({"audit_chain", "retention_overdue", "master_key", "fairness_run", "dpia"} <= ids)
        by_id = {check["id"]: check for check in response.data["checks"]}
        self.assertEqual(by_id["audit_chain"]["status"], "pass")
        self.assertEqual(by_id["fairness_run"]["status"], "fail")   # never run yet
        self.assertEqual(by_id["dpia"]["status"], "manual")
        self.assertIn("not legal advice", response.data["disclaimer"].lower())
        self.assertEqual(sum(response.data["counts"].values()), len(response.data["checks"]))

    def test_recruiter_cannot_open_the_report(self):
        self.assertEqual(client_for(make_user("recruiter")).get("/api/compliance/").status_code, 403)
