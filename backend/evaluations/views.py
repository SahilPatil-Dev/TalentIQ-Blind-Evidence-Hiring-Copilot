"""
API views: one small function per URL (the list of URLs is in urls.py).

The main flow, when a recruiter uploads a resume (upload_application):

  1. read the text out of the file (PDF / TXT / MD)
  2. redact_resume()      -> remove name, email, phone, university, pronouns
  3. evaluate_candidate() -> the AI flow finds quotes + Python calculates a score
  4. save everything (identity is saved ENCRYPTED)
  5. send back the result WITHOUT any identity

Identity is never part of a normal response. After a candidate is shortlisted,
an admin or recruiter can call reveal_identity() with a written reason; every
reveal is written to the audit log.

Every endpoint needs a signed-in user with the right role (see auth.py).
"""
import pymupdf  # PDF text extraction
from cryptography.fernet import InvalidToken
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.exceptions import APIException, NotFound
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from .auth import ADMIN, CAN_MANAGE_HIRING, CAN_VIEW_CANDIDATES, has_role
from .models import AuditLog, CandidateApplication, EncryptionKey, JobRole
from .serializers import CandidateApplicationSerializer, JobRoleSerializer
from .services.evaluator import evaluate_candidate
from .services.audit import log_event
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


class UploadThrottle(UserRateThrottle):
    """Limits how many resumes one signed-in user can upload per hour (see settings)."""

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
@authentication_classes([])
@permission_classes([AllowAny])
def health(request):
    """Used by Render (and the website) to check that the server is awake."""
    return Response({"status": "ok"})


@api_view(["GET", "POST"])
@parser_classes([JSONParser])
@permission_classes([has_role(*CAN_VIEW_CANDIDATES)])
def jobs(request):
    """GET = list all roles. POST = create a new role (recruiter/admin only)."""
    if request.method == "GET":
        return Response(JobRoleSerializer(JobRole.objects.all(), many=True).data)

    if not has_role(*CAN_MANAGE_HIRING)().has_permission(request, None):
        return Response({"detail": "Your role cannot create roles."}, status=status.HTTP_403_FORBIDDEN)
    serializer = JobRoleSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    role = serializer.save()
    log_event(request, "job.create", "job", role.id, {"title": role.title})
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([has_role(*CAN_VIEW_CANDIDATES)])
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
@permission_classes([has_role(*CAN_MANAGE_HIRING)])
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
    log_event(request, "application.upload", "application", application.id, {"job_id": job.id})
    return Response(
        CandidateApplicationSerializer(application).data,
        status=status.HTTP_201_CREATED,
    )


def _application_payload(application):
    """Blind view of a candidate, plus who has revealed the identity and why."""
    payload = CandidateApplicationSerializer(application).data
    payload["reveal_history"] = [
        {
            "by": entry.actor_email,
            "reason": entry.detail.get("reason", ""),
            "at": entry.created_at,
        }
        for entry in AuditLog.objects.filter(
            action="identity.reveal", target_type="application", target_id=str(application.id)
        ).order_by("-id")[:20]
    ]
    return payload


@api_view(["GET", "DELETE"])
@permission_classes([has_role(*CAN_VIEW_CANDIDATES)])
def application_detail(request, application_id):
    """GET: one candidate's blind evidence review. DELETE: erase it (admin only)."""
    application = get_or_404(CandidateApplication, application_id, "Application")

    if request.method == "DELETE":
        if not has_role(ADMIN)().has_permission(request, None):
            return Response({"detail": "Only administrators can delete candidates."},
                            status=status.HTTP_403_FORBIDDEN)
        if application.legal_hold:
            return Response({"detail": "This candidate is under legal hold."},
                            status=status.HTTP_409_CONFLICT)
        log_event(request, "application.delete", "application", application.id,
                  {"job_id": application.job_id, "reason": str(request.data.get("reason", ""))[:300]})
        application.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    return Response(_application_payload(application))


@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([has_role(*CAN_MANAGE_HIRING)])
def decide_application(request, application_id):
    """The human decision: {"decision": "shortlist"|"reject", "reason": "..."}."""
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
    reason = str(request.data.get("reason", "")).strip()
    if len(reason) < 5:
        raise BadRequest("Write a short reason for your decision (at least 5 characters).")

    application.status = (
        CandidateApplication.Status.SHORTLISTED
        if decision == "shortlist"
        else CandidateApplication.Status.REJECTED
    )
    application.decided_at = timezone.now()
    application.decided_by = request.user
    application.decision_reason = reason[:1000]
    application.save(update_fields=["status", "decided_at", "decided_by", "decision_reason"])
    log_event(request, f"application.{decision}", "application", application.id,
              {"score": application.final_score, "reason": application.decision_reason})
    return Response(CandidateApplicationSerializer(application).data)


@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([has_role(*CAN_MANAGE_HIRING)])
def reveal_identity(request, application_id):
    """Audited identity reveal: shortlisted candidates only, with a written reason."""
    application = get_or_404(CandidateApplication, application_id, "Application")
    if application.status != CandidateApplication.Status.SHORTLISTED:
        return Response({"detail": "Identity can only be revealed for shortlisted candidates."},
                        status=status.HTTP_409_CONFLICT)
    reason = str(request.data.get("reason", "")).strip()
    if len(reason) < 10:
        raise BadRequest("Explain why you need the identity (at least 10 characters).")

    try:
        identity = decrypt_pii(application.encrypted_pii)
    except (InvalidToken, EncryptionKey.DoesNotExist, ValueError):
        return Response({"detail": "This identity can no longer be decrypted (its key is missing)."},
                        status=status.HTTP_409_CONFLICT)
    # Log first: if logging fails, nothing is revealed.
    log_event(request, "identity.reveal", "application", application.id,
              {"reason": reason[:500], "fields": sorted(identity.keys())})
    return Response({"identity": identity})


@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([has_role(ADMIN)])
def set_legal_hold(request, application_id):
    """Admin: {"legal_hold": true|false, "reason": "..."} pauses or resumes deletion."""
    application = get_or_404(CandidateApplication, application_id, "Application")
    hold = request.data.get("legal_hold")
    if not isinstance(hold, bool):
        raise BadRequest("legal_hold must be true or false.")
    application.legal_hold = hold
    application.save(update_fields=["legal_hold"])
    log_event(request, "application.legal_hold", "application", application.id,
              {"legal_hold": hold, "reason": str(request.data.get("reason", ""))[:300]})
    return Response(CandidateApplicationSerializer(application).data)
