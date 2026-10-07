import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0003_integration_settings"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DirectEmailNotification",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("to_recipients", models.JSONField(default=list)),
                ("cc_recipients", models.JSONField(blank=True, default=list)),
                ("bcc_recipients", models.JSONField(blank=True, default=list)),
                ("subject", models.CharField(max_length=255)),
                ("body", models.TextField()),
                ("scheduled_for", models.DateTimeField(blank=True, null=True)),
                ("schedule_timezone", models.CharField(default="UTC", max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("SCHEDULED", "Scheduled"),
                            ("SENDING", "Sending"),
                            ("SENT", "Sent"),
                            ("FAILED", "Failed"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="DRAFT",
                        max_length=16,
                    ),
                ),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_direct_email_notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "legal_entity",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="direct_email_notifications",
                        to="identity.legalentity",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="direct_email_notifications",
                        to="identity.organization",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="directemailnotification",
            index=models.Index(
                fields=["organization", "status", "scheduled_for"],
                name="direct_email_due_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="directemailnotification",
            index=models.Index(
                fields=["legal_entity", "created_at"],
                name="direct_email_entity_idx",
            ),
        ),
    ]
