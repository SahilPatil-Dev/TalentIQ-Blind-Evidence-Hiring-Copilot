"""
API views: one small function per URL (the list of URLs is in urls.py).

The main flow, when a recruiter uploads a resume (upload_application):

  1. read the text out of the file (PDF / TXT / MD)
  2. redact_resume()      -> remove name, email, phone, university, pronouns
  3. evaluate_candidate() -> the AI flow finds quotes + Python calculates a score
  4. save everything (identity is saved ENCRYPTED)
  5. send back the result WITHOUT any identity

Identity is only returned later by application_detail(), and only after the
recruiter has shortlisted that candidate.
"""
import pymupdf  # PDF text extraction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, throttle_classes
from rest_framework.exceptions import APIException, NotFound
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .models import CandidateApplication, JobRole
from .serializers import CandidateApplicationSerializer, JobRoleSerializer
from .services.evaluator import evaluate_candidate
from .services.mistral import MistralAPIError
from .services.privacy import decrypt_pii, encrypt_pii, redact_resume

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB upload limit
MAX_RESUME_CHARS = 30_000          # keeps AI cost and response time under control


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
class BadRequest(APIException):
    """A 400 error that is sent as {"detail": "message"}."""

    status_code = 400
    default_code = "bad_request"


class UploadThrottle(AnonRateThrottle):
    """Limits how many resumes one visitor can upload per hour (see settings)."""

    scope = "upload"


def get_or_404(model, pk, label):
    """Return the row with this id, or answer 404 "<label> not found."."""
    try:
        return model.objects.get(pk=pk)
    except model.DoesNotExist:
        raise NotFound(f"{label} not found.")


def read_resume_text(request):
    """Get the resume text from an uploaded file OR from a `resume_text` field."""
    uploaded_file = request.FILES.get("resume")

    if uploaded_file:
        if uploaded_file.size > MAX_FILE_BYTES:
            raise BadRequest("Resume file must be 10 MB or smaller.")

        name = uploaded_file.name.lower()
        if name.endswith(".pdf"):
            try:
                document = pymupdf.open(stream=uploaded_file.read(), filetype="pdf")
            except (pymupdf.FileDataError, RuntimeError):
                raise BadRequest("The uploaded PDF could not be read.")
            text = "\n".join(page.get_text() for page in document)
            document.close()
        elif name.endswith((".txt", ".md")):
            text = uploaded_file.read().decode("utf-8", errors="replace")
        else:
            raise BadRequest("Upload a PDF, TXT, or Markdown resume.")
    else:
        text = request.data.get("resume_text", "")

    if not text or not text.strip():
        raise BadRequest("Provide a non-empty resume file or resume_text.")
    return text[:MAX_RESUME_CHARS]


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------
@api_view(["GET"])
def health(request):
    """Used by Render (and the website) to check that the server is awake."""
    return Response({"status": "ok"})


@api_view(["GET", "POST"])
@parser_classes([JSONParser])
def jobs(request):
    """GET = list all roles. POST = create a new role."""
    if request.method == "GET":
        return Response(JobRoleSerializer(JobRole.objects.all(), many=True).data)

    serializer = JobRoleSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def job_detail(request, job_id):
    """One role plus all of its candidates (already ranked by score)."""
    job = get_or_404(JobRole, job_id, "Role")
    payload = JobRoleSerializer(job).data
    payload["applications"] = CandidateApplicationSerializer(
        job.applications.all(), many=True
    ).data
    return Response(payload)


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser, JSONParser])
@throttle_classes([UploadThrottle])
def upload_application(request, job_id):
    """Upload a resume for a role. This is where the whole AI flow runs."""
    job = get_or_404(JobRole, job_id, "Role")
    resume_text = read_resume_text(request)

    # Step 1: hide identity. `pii` holds the removed details (name, email...).
    redacted_text, pii = redact_resume(resume_text)

    # Step 2: evaluate ONLY the redacted text. If Mistral fails we answer 502
    # instead of silently guessing.
    try:
        evaluation = evaluate_candidate(redacted_text, job.rubric_criteria)
    except MistralAPIError as error:
        return Response({"detail": str(error)}, status=status.HTTP_502_BAD_GATEWAY)

    # Step 3: save. The identity is encrypted before it touches the database.
    application = CandidateApplication.objects.create(
        job=job,
        redacted_text=redacted_text,
        encrypted_pii=encrypt_pii(pii),
        status=CandidateApplication.Status.NEEDS_REVIEW,
        **evaluation,
    )
    return Response(
        CandidateApplicationSerializer(application).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
def application_detail(request, application_id):
    """One candidate's evidence review. Identity appears only after shortlisting."""
    application = get_or_404(CandidateApplication, application_id, "Application")
    payload = CandidateApplicationSerializer(application).data

    if application.status == CandidateApplication.Status.SHORTLISTED:
        payload["identity"] = decrypt_pii(application.encrypted_pii)
    return Response(payload)


@api_view(["POST"])
@parser_classes([JSONParser])
def decide_application(request, application_id):
    """The human decision: {"decision": "shortlist"} or {"decision": "reject"}."""
    application = get_or_404(CandidateApplication, application_id, "Application")

    # A decision can only be made once.
    if application.status != CandidateApplication.Status.NEEDS_REVIEW:
        return Response(
            {"detail": "A decision has already been recorded."},
            status=status.HTTP_409_CONFLICT,
        )

    decision = request.data.get("decision")
    if decision not in ("shortlist", "reject"):
        raise BadRequest("Decision must be 'shortlist' or 'reject'.")

    application.status = (
        CandidateApplication.Status.SHORTLISTED
        if decision == "shortlist"
        else CandidateApplication.Status.REJECTED
    )
    application.decided_at = timezone.now()
    application.save(update_fields=["status", "decided_at"])
    return Response(CandidateApplicationSerializer(application).data)
