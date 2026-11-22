"""
Governance endpoints: audit log, retention, encryption keys, fairness, compliance.
Admins can do everything here; auditors can read (audit, fairness, compliance, retention).
"""
import csv

from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from .auth import ADMIN, CAN_SEE_GOVERNANCE, has_role
from .models import AuditLog, CandidateApplication, FairnessRun
from .services import compliance, fairness, keys, retention
from .services.audit import log_event, verify_chain
from .views import BadRequest

MAX_DAYS = 3650


def _audit_row(entry):
    return {
        "id": entry.id, "at": entry.created_at, "actor": entry.actor_email, "action": entry.action,
        "target_type": entry.target_type, "target_id": entry.target_id, "detail": entry.detail,
        "ip": entry.ip_address, "hash": entry.entry_hash[:12],
    }


@api_view(["GET"])
@permission_classes([has_role(*CAN_SEE_GOVERNANCE)])
def audit_log(request):
    """Newest first. Filters: ?action=identity.reveal&limit=100&before=<id>. ?format=csv exports."""
    entries = AuditLog.objects.order_by("-id")
    if request.query_params.get("action"):
        entries = entries.filter(action=request.query_params["action"])
    if request.query_params.get("before", "").isdigit():
        entries = entries.filter(id__lt=int(request.query_params["before"]))
    limit = 5000 if request.query_params.get("format") == "csv" else 100
    rows = [_audit_row(entry) for entry in entries[:limit]]

    if request.query_params.get("format") == "csv":
        log_event(request, "audit.export", "audit", "", {"rows": len(rows)})
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="talentiq-audit-log.csv"'
        writer = csv.writer(response)
        writer.writerow(["id", "time", "actor", "action", "target_type", "target_id", "detail", "ip", "hash"])
        for row in rows:
            writer.writerow([row["id"], row["at"], row["actor"], row["action"], row["target_type"],
                             row["target_id"], row["detail"], row["ip"], row["hash"]])
        return response
    return Response(rows)


@api_view(["GET"])
@permission_classes([has_role(*CAN_SEE_GOVERNANCE)])
def audit_verify(request):
    result = verify_chain()
    log_event(request, "audit.verify", "audit", "", {"valid": result["valid"]})
    return Response(result)


# ---------------- Retention ----------------
def _policy_payload(policy):
    return {
        "rejected_days": policy.rejected_days,
        "undecided_days": policy.undecided_days,
        "shortlisted_days": policy.shortlisted_days,
        "last_run_at": policy.last_run_at,
        "last_run_deleted": policy.last_run_deleted,
        "due_now": len(retention.find_expired(policy)),
        "on_legal_hold": CandidateApplication.objects.filter(legal_hold=True).count(),
    }


@api_view(["GET", "PUT"])
@parser_classes([JSONParser])
@permission_classes([has_role(*CAN_SEE_GOVERNANCE)])
def retention_policy(request):
    policy = retention.get_policy()
    if request.method == "PUT":
        if not has_role(ADMIN)().has_permission(request, None):
            return Response({"detail": "Only administrators can change the policy."},
                            status=status.HTTP_403_FORBIDDEN)
        changes = {}
        for field in ("rejected_days", "undecided_days", "shortlisted_days"):
            if field in request.data:
                value = request.data[field]
                if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_DAYS:
                    raise BadRequest(f"{field} must be a whole number of days from 1 to {MAX_DAYS}.")
                changes[field] = value
        for field, value in changes.items():
            setattr(policy, field, value)
        policy.save()
        log_event(request, "retention.policy_update", "retention", policy.id, changes)
    return Response(_policy_payload(policy))


@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([has_role(ADMIN)])
def retention_run(request):
    """{"dry_run": true} previews what would be deleted."""
    dry_run = request.data.get("dry_run", True) is not False
    return Response(retention.enforce(dry_run=dry_run, request=request))


# ---------------- Encryption keys ----------------
@api_view(["GET"])
@permission_classes([has_role(ADMIN)])
def key_status(request):
    return Response(keys.key_report())


@api_view(["POST"])
@permission_classes([has_role(ADMIN)])
def key_rotate(request):
    row = keys.rotate_data_key()
    log_event(request, "key.rotate", "key", row.version, {"version": row.version})
    return Response(keys.key_report(), status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([has_role(ADMIN)])
def key_reencrypt(request):
    moved = keys.reencrypt_all()
    log_event(request, "key.reencrypt", "key", "", {"records": moved})
    return Response({"records_reencrypted": moved, **keys.key_report()})


# ---------------- Fairness ----------------
def _run_payload(run, with_details=True):
    data = {"id": run.id, "created_at": run.created_at,
            "by": run.created_by.email if run.created_by else "", "passed": run.passed, "summary": run.summary}
    if with_details:
        data["details"] = run.details
    return data


@api_view(["GET", "POST"])
@parser_classes([JSONParser])
@permission_classes([has_role(*CAN_SEE_GOVERNANCE)])
def fairness_runs(request):
    if request.method == "GET":
        return Response([_run_payload(run, False) for run in FairnessRun.objects.select_related("created_by")[:20]])
    passed, summary, details = fairness.run_counterfactual_suite()
    run = FairnessRun.objects.create(created_by=request.user, passed=passed, summary=summary, details=details)
    log_event(request, "fairness.run", "fairness", run.id, {"passed": passed, **{
        k: summary[k] for k in ("variants_tested", "variants_leaking", "max_score_difference")}})
    return Response(_run_payload(run), status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([has_role(*CAN_SEE_GOVERNANCE)])
def fairness_run_detail(request, run_id):
    run = FairnessRun.objects.select_related("created_by").filter(pk=run_id).first()
    if run is None:
        return Response({"detail": "Run not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response(_run_payload(run))


@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([has_role(*CAN_SEE_GOVERNANCE)])
def adverse_impact(request):
    """{"groups": [{"name": "A", "applicants": 100, "selected": 20}, ...]}"""
    groups = request.data.get("groups")
    if not isinstance(groups, list):
        raise BadRequest("Provide a list of groups.")
    try:
        result = fairness.four_fifths(groups)
    except (ValueError, KeyError, TypeError) as error:
        raise BadRequest(str(error) or "Check the group numbers.")
    log_event(request, "fairness.adverse_impact", "fairness", "", {"groups": len(groups), "flagged": result["any_flag"]})
    return Response(result)


# ---------------- Compliance ----------------
@api_view(["GET"])
@permission_classes([has_role(*CAN_SEE_GOVERNANCE)])
def compliance_report(request):
    return Response(compliance.build_report())
