import json
from datetime import date
from functools import wraps
from pathlib import Path

from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError, transaction
from django.db import models
from django.http import FileResponse, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .bulksms import MessageNotSendable, ProviderNotConfigured, send_outbox_message
from .models import AuditEvent, CommunicationConsent, DeskCounter, MessageOutbox, Patient, UltrasoundReport, Visit


def api_login_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Please sign in."}, status=401)
        return view(request, *args, **kwargs)
    return wrapped


def body_json(request):
    try:
        return json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("Request body must be valid JSON.")


def bad_request(message, status=400):
    return JsonResponse({"error": message}, status=status)


def record_audit(user, action, obj, details=None):
    AuditEvent.objects.create(actor=user, action=action, object_type=obj.__class__.__name__, object_id=str(obj.pk), details=details or {})


@api_login_required
def counters_api(request):
    if request.method == "POST":
        try:
            key = body_json(request).get("key")
        except ValueError as exc:
            return bad_request(str(exc))
        if key not in ("opd_printed", "ultrasound_saved"):
            return bad_request("Unknown counter.")
        counter, _ = DeskCounter.objects.get_or_create(key=key)
        DeskCounter.objects.filter(key=key).update(value=models.F("value") + 1)
    return JsonResponse({"opd": DeskCounter.objects.filter(key="opd_printed").values_list("value", flat=True).first() or 0,
                         "ultrasound": DeskCounter.objects.filter(key="ultrasound_saved").values_list("value", flat=True).first() or 0})


def set_consent(patient, purpose, allowed, user):
    if not allowed:
        return None
    consent, _ = CommunicationConsent.objects.update_or_create(
        patient=patient, purpose=purpose, channel="sms_or_whatsapp",
        defaults={"consented": True, "recorded_by": user},
    )
    return consent


def maybe_queue(patient, purpose, allowed, user, *, visit=None, report=None):
    if not allowed:
        return
    set_consent(patient, purpose, True, user)
    key = f"{purpose}:{visit.pk if visit else report.pk}"
    MessageOutbox.objects.get_or_create(
        idempotency_key=key,
        defaults={"patient": patient, "purpose": purpose, "visit": visit, "report": report,
                  "status": MessageOutbox.Status.REVIEW, "consent_confirmed": True, "created_by": user},
    )


def patient_for(payload, user):
    name = str(payload.get("name", "")).strip()
    if not name:
        raise ValueError("Patient name is required.")
    record_number = str(payload.get("pid", "")).strip()
    if record_number:
        patient, created = Patient.objects.get_or_create(
            record_number=record_number,
            defaults={"name": name, "age": str(payload.get("age", ""))[:40], "sex": str(payload.get("sex", ""))[:24], "phone": str(payload.get("phone", ""))[:32]},
        )
        if not created:
            patient.name = name
            patient.age = str(payload.get("age", patient.age))[:40]
            patient.sex = str(payload.get("sex", patient.sex))[:24]
            patient.phone = str(payload.get("phone", patient.phone))[:32]
            patient.save(update_fields=["name", "age", "sex", "phone"])
    else:
        patient = Patient.objects.create(name=name, age=str(payload.get("age", ""))[:40], sex=str(payload.get("sex", ""))[:24], phone=str(payload.get("phone", ""))[:32])
    return patient


def serialize_visit(item):
    return {"kind": "OPD", "id": str(item.pk), "name": item.patient.name, "pid": item.patient.record_number,
            "date": item.visit_date.isoformat(), "age": item.patient.age, "sex": item.patient.sex,
            "phone": item.patient.phone, "complaints": item.complaints, "diagnosis": item.diagnosis,
            "prescription": item.prescription, "status": "Saved"}


def serialize_report(item):
    return {"kind": "US", "id": str(item.pk), "name": item.patient.name, "pid": item.patient.record_number,
            "date": item.report_date.isoformat(), "demographics": item.demographics, "type": item.report_type,
            "indication": item.indication, "findings": item.findings, "measurements": item.measurements,
            "impression": item.impression, "status": "Ready" if item.status == UltrasoundReport.Status.READY else "Draft",
            "permission": item.patient.communication_consents.filter(purpose=CommunicationConsent.Purpose.REPORT_READY, consented=True).exists()}


def app_shell(request):
    return FileResponse(open(Path(__file__).resolve().parents[2] / "index.html", "rb"), content_type="text/html; charset=utf-8")


@ensure_csrf_cookie
@require_GET
def session_info(request):
    return JsonResponse({"authenticated": request.user.is_authenticated,
                         "username": request.user.get_username() if request.user.is_authenticated else None,
                         "csrfToken": get_token(request)})


@require_POST
def login_view(request):
    try:
        payload = body_json(request)
    except ValueError as exc:
        return bad_request(str(exc))
    user = authenticate(request, username=payload.get("username", ""), password=payload.get("password", ""))
    if user is None or not user.is_active:
        return bad_request("Username or password is incorrect.", 401)
    login(request, user)
    return JsonResponse({"authenticated": True, "username": user.get_username()})


@require_POST
@api_login_required
def logout_view(request):
    logout(request)
    return JsonResponse({"authenticated": False})


@api_login_required
def visits_api(request):
    if request.method == "GET":
        return JsonResponse({"items": [serialize_visit(x) for x in Visit.objects.select_related("patient").all()[:3]]})
    if request.method == "POST":
        return visits_create(request)
    return bad_request("Method not allowed.", 405)


def visits_create(request):
    try:
        payload = body_json(request)
        visit_date = date.fromisoformat(str(payload.get("date", "")))
        with transaction.atomic():
            patient = patient_for(payload, request.user)
            visit = Visit.objects.create(patient=patient, visit_date=visit_date,
                complaints=str(payload.get("complaints", "")), diagnosis=str(payload.get("diagnosis", "")),
                prescription=str(payload.get("prescription", "")), created_by=request.user)
            # OPD is a short working list: keep this patient's three newest visits.
            retained_ids = list(Visit.objects.filter(patient=patient).order_by("-created_at").values_list("pk", flat=True)[:3])
            Visit.objects.filter(patient=patient).exclude(pk__in=retained_ids).delete()
            maybe_queue(patient, CommunicationConsent.Purpose.THANK_YOU, payload.get("permission", False), request.user, visit=visit)
            record_audit(request.user, "visit_saved", visit)
        return JsonResponse(serialize_visit(visit), status=201)
    except ValueError as exc:
        return bad_request(str(exc))
    except IntegrityError:
        return bad_request("That patient ID is already in use. Please check it and try again.", 409)


def reports_create(request):
    try:
        payload = body_json(request)
        report_date = date.fromisoformat(str(payload.get("date", "")))
        report_id = payload.get("id")
        with transaction.atomic():
            patient = patient_for(payload, request.user)
            if report_id:
                report = UltrasoundReport.objects.select_for_update().get(pk=report_id)
                if report.status == UltrasoundReport.Status.READY:
                    return bad_request("Finalized reports cannot be overwritten. Create a new report or addendum.", 409)
                if report.patient_id != patient.pk:
                    return bad_request("A draft cannot be moved to another patient.", 409)
                report.report_type = payload.get("type", report.report_type)
                report.report_date = report_date
                report.demographics = str(payload.get("demographics", ""))
                report.indication = str(payload.get("indication", ""))
                report.findings = str(payload.get("findings", ""))
                report.measurements = str(payload.get("measurements", ""))
                report.impression = str(payload.get("impression", ""))
            else:
                report = UltrasoundReport(patient=patient, report_type=payload.get("type", "CEPHALIC"), report_date=report_date, created_by=request.user)
                report.demographics = str(payload.get("demographics", ""))
                report.indication = str(payload.get("indication", ""))
                report.findings = str(payload.get("findings", ""))
                report.measurements = str(payload.get("measurements", ""))
                report.impression = str(payload.get("impression", ""))
            if report.report_type not in dict(UltrasoundReport.REPORT_TYPES):
                return bad_request("Choose a valid ultrasound report type.")
            if payload.get("finalize"):
                report.status = UltrasoundReport.Status.READY
                report.finalized_by = request.user
                from django.utils import timezone
                report.finalized_at = timezone.now()
            report.save()
            report.plain_text = "\n".join([f"{k}: {v}" for k, v in {
                "id": report.pk, "patient": patient.name, "patient_id": patient.record_number,
                "date": report.report_date, "type": report.report_type, "demographics": report.demographics,
                "indication": report.indication, "findings": report.findings,
                "measurements": report.measurements, "impression": report.impression,
                "status": report.status,
            }.items()])
            report.save(update_fields=["plain_text"])
            if report.status == UltrasoundReport.Status.READY:
                maybe_queue(patient, CommunicationConsent.Purpose.REPORT_READY, payload.get("permission", False), request.user, report=report)
            elif payload.get("permission", False):
                set_consent(patient, CommunicationConsent.Purpose.REPORT_READY, True, request.user)
            record_audit(request.user, "report_finalized" if report.status == UltrasoundReport.Status.READY else "report_saved", report, {"version": report.version})
        return JsonResponse(serialize_report(report), status=201)
    except UltrasoundReport.DoesNotExist:
        return bad_request("Report was not found.", 404)
    except ValueError as exc:
        return bad_request(str(exc))


@api_login_required
def reports_api(request):
    if request.method == "GET":
        return JsonResponse({"items": [serialize_report(x) for x in UltrasoundReport.objects.select_related("patient").all()[:500]]})
    if request.method == "POST":
        return reports_create(request)
    return bad_request("Method not allowed.", 405)


@require_GET
@api_login_required
def archive_api(request):
    visits = [serialize_visit(x) for x in Visit.objects.select_related("patient").all()[:3]]
    reports = [serialize_report(x) for x in UltrasoundReport.objects.select_related("patient").all()]
    return JsonResponse({"items": sorted(visits + reports, key=lambda x: x["date"], reverse=True)})


@require_GET
@api_login_required
def messages_api(request):
    items = []
    for msg in MessageOutbox.objects.select_related("patient").exclude(status=MessageOutbox.Status.CANCELLED)[:500]:
        ready = msg.purpose == CommunicationConsent.Purpose.REPORT_READY
        consented = msg.patient.communication_consents.filter(purpose=msg.purpose, consented=True).exists()
        phone = msg.patient.phone or ""
        masked_phone = ("••••" + phone[-4:]) if len(phone) >= 4 else "Not on file"
        items.append({"id": str(msg.pk), "recordId": str(msg.report_id or msg.visit_id), "name": msg.patient.name,
            "purpose": "Report ready" if ready else "Thank you", "channel": "SMS via BulkSMS",
            "preview": "Your report is ready. Please contact the hospital." if ready else "Thank you for visiting us. We wish you well.",
            "status": msg.get_status_display(), "maskedPhone": masked_phone,
            "canSend": msg.status == MessageOutbox.Status.REVIEW and consented and bool(phone)})
    return JsonResponse({"items": items})


@require_POST
@api_login_required
def send_message_api(request, message_id):
    try:
        status = send_outbox_message(message_id, request.user)
    except MessageOutbox.DoesNotExist:
        return bad_request("Message was not found.", 404)
    except ProviderNotConfigured as exc:
        return bad_request(str(exc), 503)
    except MessageNotSendable as exc:
        return bad_request(str(exc), 409)
    return JsonResponse({"status": status, "message": MessageOutbox.Status(status).label})
