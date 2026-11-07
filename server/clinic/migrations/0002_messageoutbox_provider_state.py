from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("clinic", "0001_initial")]
    operations = [
        migrations.AlterField(
            model_name="messageoutbox",
            name="status",
            field=models.CharField(choices=[
                ("review_required", "Review required"),
                ("sending", "Sending"),
                ("submitted", "Submitted to provider"),
                ("failed", "Failed"),
                ("unknown", "Delivery state unknown"),
                ("cancelled", "Cancelled"),
            ], default="review_required", max_length=24),
        ),
        migrations.AddField(model_name="messageoutbox", name="provider_message_id", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="messageoutbox", name="attempted_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="messageoutbox", name="last_error", field=models.CharField(blank=True, max_length=300)),
    ]
