import django.db.models.deletion
import django.db.models.functions.text
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0001_initial"),
        ("notifications", "0006_email_template_designer"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CentralEmailRecipient",
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
                ("name", models.CharField(blank=True, max_length=180)),
                ("email", models.EmailField(max_length=254)),
                (
                    "recipient_type",
                    models.CharField(
                        choices=[("TO", "To"), ("CC", "Cc"), ("BCC", "Bcc")],
                        default="TO",
                        max_length=8,
                    ),
                ),
                ("enabled", models.BooleanField(default=True)),
                ("event_types", models.JSONField(blank=True, default=list)),
                ("attach_documents", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_central_email_recipients",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="central_email_recipients",
                        to="identity.organization",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_central_email_recipients",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["email"],
            },
        ),
        migrations.AddConstraint(
            model_name="centralemailrecipient",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower("email"),
                "organization",
                name="uniq_central_email_recipient_ci",
            ),
        ),
        migrations.AddIndex(
            model_name="centralemailrecipient",
            index=models.Index(
                fields=["organization", "enabled"],
                name="central_email_org_enabled_idx",
            ),
        ),
    ]
