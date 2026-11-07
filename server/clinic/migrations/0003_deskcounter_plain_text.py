from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("clinic", "0002_messageoutbox_provider_state")]

    operations = [
        migrations.CreateModel(
            name="DeskCounter",
            fields=[
                ("key", models.CharField(max_length=24, primary_key=True, serialize=False)),
                ("value", models.PositiveBigIntegerField(default=0)),
            ],
        ),
        migrations.AddField(
            model_name="ultrasoundreport",
            name="plain_text",
            field=models.TextField(blank=True),
        ),
    ]
