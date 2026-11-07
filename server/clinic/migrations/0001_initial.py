import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models
import clinic.models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="Patient", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("record_number", models.CharField(default=clinic.models.make_record_number, max_length=16, unique=True)),
            ("name", models.CharField(max_length=160)), ("age", models.CharField(blank=True, max_length=40)),
            ("sex", models.CharField(blank=True, max_length=24)), ("phone", models.CharField(blank=True, max_length=32)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
        ]),
        migrations.CreateModel(name="Visit", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("visit_date", models.DateField()), ("complaints", models.TextField(blank=True)),
            ("diagnosis", models.TextField(blank=True)), ("prescription", models.TextField(blank=True)),
            ("status", models.CharField(default="saved", max_length=20)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_visits", to=settings.AUTH_USER_MODEL)),
            ("patient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="visits", to="clinic.patient")),
        ], options={"ordering": ["-created_at"]}),
        migrations.CreateModel(name="UltrasoundReport", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("report_type", models.CharField(choices=[("BLIGHTED OVUM", "BLIGHTED OVUM"), ("BREECH", "BREECH"), ("CEPHALIC", "CEPHALIC"), ("CRL", "CRL"), ("LEVEL 2", "LEVEL 2"), ("RPOC", "RPOC"), ("TRANSVERSE", "TRANSVERSE"), ("VARIABLE", "VARIABLE")], max_length=32)),
            ("report_date", models.DateField()), ("demographics", models.CharField(blank=True, max_length=80)),
            ("indication", models.TextField(blank=True)), ("findings", models.TextField(blank=True)),
            ("measurements", models.TextField(blank=True)), ("impression", models.TextField(blank=True)),
            ("status", models.CharField(choices=[("draft", "Draft"), ("ready", "Ready")], default="draft", max_length=16)),
            ("version", models.PositiveIntegerField(default=1)), ("finalized_at", models.DateTimeField(blank=True, null=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_reports", to=settings.AUTH_USER_MODEL)),
            ("finalized_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="finalized_reports", to=settings.AUTH_USER_MODEL)),
            ("patient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reports", to="clinic.patient")),
        ], options={"ordering": ["-created_at"]}),
        migrations.CreateModel(name="CommunicationConsent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("purpose", models.CharField(choices=[("thank_you", "Thank-you message"), ("report_ready", "Report-ready notification")], max_length=24)),
            ("channel", models.CharField(default="sms_or_whatsapp", max_length=20)), ("consented", models.BooleanField(default=False)),
            ("recorded_at", models.DateTimeField(auto_now=True)),
            ("patient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="communication_consents", to="clinic.patient")),
            ("recorded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="MessageOutbox", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("purpose", models.CharField(choices=[("thank_you", "Thank-you message"), ("report_ready", "Report-ready notification")], max_length=24)),
            ("status", models.CharField(choices=[("review_required", "Review required"), ("queued", "Queued"), ("cancelled", "Cancelled")], default="review_required", max_length=24)),
            ("consent_confirmed", models.BooleanField(default=False)), ("idempotency_key", models.CharField(max_length=100, unique=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ("patient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="messages", to="clinic.patient")),
            ("report", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="clinic.ultrasoundreport")),
            ("visit", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="clinic.visit")),
        ], options={"ordering": ["-created_at"]}),
        migrations.CreateModel(name="AuditEvent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("action", models.CharField(max_length=40)), ("object_type", models.CharField(max_length=40)),
            ("object_id", models.CharField(max_length=64)), ("details", models.JSONField(blank=True, default=dict)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["-created_at"]}),
        migrations.AddConstraint(model_name="communicationconsent", constraint=models.UniqueConstraint(fields=("patient", "purpose", "channel"), name="uniq_patient_consent_purpose_channel")),
    ]
