"""
`python manage.py seed_demo` creates a sample role and six made-up candidates so
the dashboard isn't empty on first launch. It is safe to run many times: it
skips anything that already exists.

It always uses the local keyword matcher (use_ai=False), so starting the server
never spends Mistral credits.
"""
from django.core.management.base import BaseCommand

from evaluations.models import CandidateApplication, JobRole
from evaluations.services.evaluator import evaluate_candidate
from evaluations.services.privacy import encrypt_pii, redact_resume

# The sample role's rubric (weights add up to 100).
CRITERIA = [
    {"name": "Python backend", "weight": 40, "keywords": ["Python", "Django", "REST API"]},
    {"name": "AI agents", "weight": 35, "keywords": ["LangGraph", "RAG", "AI agents"]},
    {"name": "System design", "weight": 25, "keywords": ["PostgreSQL", "Redis", "Docker"]},
]

# (name, email, phone, university, resume body) - everything here is fictional.
# The bodies are written so the demo shows a nice spread of scores
# (100 / 75 / 65 / 40 / 25 / 0), including a "keyword dump" that earns nothing.
SAMPLES = [
    (
        "Avery Morgan",
        "avery@example.test",
        "+1 555 010 0101",
        "Northfield",
        "Built a Django REST API for internal tools. Developed AI agents with LangGraph and RAG. Deployed PostgreSQL and Redis services using Docker.",
    ),
    (
        "Sam Taylor",
        "sam@example.test",
        "+1 555 010 0102",
        "Lakeside",
        "Implemented Python data pipelines. Prototyped AI agents with LangGraph. Deployed services to a cloud virtual machine.",
    ),
    (
        "Jordan Lee",
        "jordan@example.test",
        "+1 555 010 0103",
        "Riverton",
        "Created a Python service with Django and a REST API. Used PostgreSQL for application data and Docker for local development.",
    ),
    (
        "Casey Kim",
        "casey@example.test",
        "+1 555 010 0104",
        "Harbor",
        "Maintained a Django REST API and wrote Python automation scripts. Collaborated with a team on product releases.",
    ),
    (
        "Riley Patel",
        "riley@example.test",
        "+1 555 010 0105",
        "Summit",
        "Designed PostgreSQL schemas and operated Redis caches. Containerized workloads with Docker. Studied databases in coursework.",
    ),
    (
        "Quinn Rivera",
        "quinn@example.test",
        "+1 555 010 0106",
        "Westgate",
        "Keywords: Python, Django, REST API, LangGraph, RAG, PostgreSQL, Redis, Docker. Completed introductory tutorials; no project experience listed.",
    ),
]


class Command(BaseCommand):
    help = "Create the TalentIQ sample role and six synthetic candidate applications."

    def handle(self, *args, **options):
        role, _ = JobRole.objects.get_or_create(
            title="Junior AI & Backend Engineer",
            defaults={
                "department": "Engineering",
                "rubric_markdown": (
                    "Evaluate practical Python backend work, AI agent experience, "
                    "and production-minded system design. Use only cited evidence."
                ),
                "rubric_criteria": CRITERIA,
            },
        )

        for name, email, phone, university, body in SAMPLES:
            # Build a fake resume, then run it through the same pipeline a real
            # upload would use.
            original = (
                f"Name: {name}\nEmail: {email}\nPhone: {phone}\n"
                f"{university} University\n\n{body}"
            )
            redacted, pii = redact_resume(original)

            already_exists = CandidateApplication.objects.filter(
                job=role, redacted_text=redacted
            ).exists()
            if already_exists:
                continue

            result = evaluate_candidate(redacted, role.rubric_criteria, use_ai=False)
            CandidateApplication.objects.create(
                job=role,
                redacted_text=redacted,
                encrypted_pii=encrypt_pii(pii),
                status=CandidateApplication.Status.NEEDS_REVIEW,
                **result,
            )
        self.stdout.write(self.style.SUCCESS("TalentIQ demo role and candidates are ready."))
