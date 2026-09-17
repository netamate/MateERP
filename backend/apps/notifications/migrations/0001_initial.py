import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("identity", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
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
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("RENEWAL_DUE", "Renewal due"),
                            ("EXPENSE_APPROVAL", "Expense approval"),
                            ("REIMBURSEMENT_APPROVAL", "Reimbursement approval"),
                            ("SYSTEM", "System"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("INFO", "Info"),
                            ("WARNING", "Warning"),
                            ("CRITICAL", "Critical"),
                        ],
                        default="INFO",
                        max_length=16,
                    ),
                ),
                ("dedupe_key", models.CharField(max_length=180)),
                ("title", models.CharField(max_length=180)),
                ("message", models.TextField()),
                ("link", models.CharField(blank=True, max_length=255)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "legal_entity",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="notifications",
                        to="identity.legalentity",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="notifications",
                        to="identity.organization",
                    ),
                ),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["resolved_at", "read_at", "-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(
                fields=("organization", "recipient", "dedupe_key"),
                name="uniq_notification_recipient_key",
            ),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["recipient", "resolved_at", "read_at", "created_at"],
                name="notification_inbox_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["legal_entity", "due_date"],
                name="notification_due_idx",
            ),
        ),
    ]
