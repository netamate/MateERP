import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0002_delivery_history"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationIntegrationSettings",
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
                ("smtp_enabled", models.BooleanField(default=False)),
                ("smtp_host", models.CharField(blank=True, max_length=255)),
                ("smtp_port", models.PositiveIntegerField(default=587)),
                ("smtp_username", models.CharField(blank=True, max_length=255)),
                ("smtp_password_encrypted", models.TextField(blank=True)),
                ("smtp_use_tls", models.BooleanField(default=True)),
                ("smtp_use_ssl", models.BooleanField(default=False)),
                ("smtp_from_name", models.CharField(blank=True, default="MateERP", max_length=180)),
                ("smtp_from_email", models.EmailField(blank=True, max_length=254)),
                ("hermes_enabled", models.BooleanField(default=False)),
                ("hermes_webhook_url", models.URLField(blank=True)),
                ("hermes_token_encrypted", models.TextField(blank=True)),
                ("hermes_default_target", models.CharField(blank=True, max_length=180)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_integration_settings",
                        to="identity.organization",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_notification_integrations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "notification integration settings",
                "verbose_name_plural": "notification integration settings",
            },
        ),
    ]
