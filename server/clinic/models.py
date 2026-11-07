import secrets
import string
import uuid

from django.conf import settings
from django.db import models


def make_record_number():
    alphabet = string.ascii_uppercase + string.digits
    return "H" + "".join(secrets.choice(alphabet) for _ in range(9))


class Patient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record_number = models.CharField(max_length=16, unique=True, default=make_record_number)
    name = models.CharField(max_length=160)
    age = models.CharField(max_length=40, blank=True)
    sex = models.CharField(max_length=24, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.record_number} · {self.name}"


class Visit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="visits")
    visit_date = models.DateField()
    complaints = models.TextField(blank=True)
    diagnosis = models.TextField(blank=True)
    prescription = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="saved")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_visits")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class DeskCounter(models.Model):
    key = models.CharField(max_length=24, primary_key=True)
    value = models.PositiveBigIntegerField(default=0)


class UltrasoundReport(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"

    REPORT_TYPES = [(v, v) for v in ("BLIGHTED OVUM", "BREECH", "CEPHALIC", "CRL", "LEVEL 2", "RPOC", "TRANSVERSE", "VARIABLE")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="reports")
    report_type = models.CharField(max_length=32, choices=REPORT_TYPES)
    report_date = models.DateField()
    demographics = models.CharField(max_length=80, blank=True)
    indication = models.TextField(blank=True)
    findings = models.TextField(blank=True)
    measurements = models.TextField(blank=True)
    impression = models.TextField(blank=True)
    plain_text = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_reports")
    finalized_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="finalized_reports")
    finalized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class CommunicationConsent(models.Model):
    class Purpose(models.TextChoices):
        THANK_YOU = "thank_you", "Thank-you message"
        REPORT_READY = "report_ready", "Report-ready notification"

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="communication_consents")
    purpose = models.CharField(max_length=24, choices=Purpose.choices)
    channel = models.CharField(max_length=20, default="sms_or_whatsapp")
    consented = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    recorded_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["patient", "purpose", "channel"], name="uniq_patient_consent_purpose_channel")]


class MessageOutbox(models.Model):
    class Status(models.TextChoices):
        REVIEW = "review_required", "Review required"
        SENDING = "sending", "Sending"
        SUBMITTED = "submitted", "Submitted to provider"
        FAILED = "failed", "Failed"
        UNKNOWN = "unknown", "Delivery state unknown"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="messages")
    visit = models.ForeignKey(Visit, null=True, blank=True, on_delete=models.PROTECT)
    report = models.ForeignKey(UltrasoundReport, null=True, blank=True, on_delete=models.PROTECT)
    purpose = models.CharField(max_length=24, choices=CommunicationConsent.Purpose.choices)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.REVIEW)
    consent_confirmed = models.BooleanField(default=False)
    idempotency_key = models.CharField(max_length=100, unique=True)
    provider_message_id = models.CharField(max_length=120, blank=True)
    attempted_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=40)
    object_type = models.CharField(max_length=40)
    object_id = models.CharField(max_length=64)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
