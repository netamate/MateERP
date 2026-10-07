import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
        ("operations", "0003_alerts_payments_and_legacy_cleanup"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationDelivery",
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
                ("delivery_key", models.CharField(max_length=255, unique=True)),
                (
                    "channel",
                    models.CharField(
                        choices=[
                            ("IN_APP", "In-app"),
                            ("EMAIL", "Email"),
                            ("HERMES", "Hermes"),
                        ],
                        max_length=16,
                    ),
                ),
                ("destination", models.CharField(blank=True, max_length=255)),
                ("reminder_days_before", models.PositiveSmallIntegerField()),
                ("due_date", models.DateField()),
                ("title", models.CharField(max_length=180)),
                ("message", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("SENT", "Sent"),
                            ("FAILED", "Failed"),
                        ],
                        default="PENDING",
                        max_length=16,
                    ),
                ),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "legal_entity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="notification_deliveries",
                        to="identity.legalentity",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="notification_deliveries",
                        to="identity.organization",
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="notification_deliveries",
                        to="operations.subscription",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="notificationdelivery",
            index=models.Index(
                fields=["subscription", "due_date", "channel"],
                name="delivery_subscription_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notificationdelivery",
            index=models.Index(
                fields=["status", "created_at"],
                name="delivery_status_idx",
            ),
        ),
        migrations.AlterField(
            model_name="notification",
            name="kind",
            field=models.CharField(
                choices=[("RENEWAL_DUE", "Renewal due"), ("SYSTEM", "System")],
                max_length=32,
            ),
        ),
    ]
