import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0005_alert_rules_and_generic_deliveries"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailTemplate",
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
                ("template_key", models.CharField(max_length=120)),
                ("name", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                (
                    "signal",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("RENEWAL_DUE", "Renewal due"),
                            ("EXPENSE_APPROVAL", "Expense approval"),
                            ("REIMBURSEMENT_APPROVAL", "Reimbursement approval"),
                            ("BUDGET_THRESHOLD", "Budget threshold"),
                            ("MISSING_INVOICE", "Missing invoice"),
                            ("INVOICE_OVERDUE", "Invoice overdue"),
                            ("RECONCILIATION_NEEDED", "Reconciliation needed"),
                            ("SYSTEM", "System"),
                        ],
                        max_length=32,
                        null=True,
                    ),
                ),
                ("subject_template", models.CharField(max_length=255)),
                ("html_body_template", models.TextField(blank=True)),
                ("text_body_template", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[("ACTIVE", "Active"), ("ARCHIVED", "Archived")],
                        default="ACTIVE",
                        max_length=16,
                    ),
                ),
                ("current_version", models.PositiveIntegerField(default=1)),
                ("is_system_default", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_email_templates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "legal_entity",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="email_templates",
                        to="identity.legalentity",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="email_templates",
                        to="identity.organization",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_email_templates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["signal", "name"]},
        ),
        migrations.CreateModel(
            name="EmailTemplateVersion",
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
                ("version_number", models.PositiveIntegerField()),
                ("name", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                (
                    "signal",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("RENEWAL_DUE", "Renewal due"),
                            ("EXPENSE_APPROVAL", "Expense approval"),
                            ("REIMBURSEMENT_APPROVAL", "Reimbursement approval"),
                            ("BUDGET_THRESHOLD", "Budget threshold"),
                            ("MISSING_INVOICE", "Missing invoice"),
                            ("INVOICE_OVERDUE", "Invoice overdue"),
                            ("RECONCILIATION_NEEDED", "Reconciliation needed"),
                            ("SYSTEM", "System"),
                        ],
                        max_length=32,
                        null=True,
                    ),
                ),
                ("subject_template", models.CharField(max_length=255)),
                ("html_body_template", models.TextField(blank=True)),
                ("text_body_template", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_email_template_versions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="notifications.emailtemplate",
                    ),
                ),
            ],
            options={"ordering": ["-version_number"]},
        ),
        migrations.AddField(
            model_name="alertrule",
            name="email_template",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="alert_rules",
                to="notifications.emailtemplate",
            ),
        ),
        migrations.AddField(
            model_name="notificationdelivery",
            name="email_template",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="notification_deliveries",
                to="notifications.emailtemplate",
            ),
        ),
        migrations.AddField(
            model_name="notificationdelivery",
            name="email_template_version",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notificationdelivery",
            name="email_subject",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="notificationdelivery",
            name="email_text_body",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="notificationdelivery",
            name="email_html_body",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="directemailnotification",
            name="template",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="direct_email_notifications",
                to="notifications.emailtemplate",
            ),
        ),
        migrations.AddField(
            model_name="directemailnotification",
            name="template_version",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="directemailnotification",
            name="html_body",
            field=models.TextField(blank=True),
        ),
        migrations.AddConstraint(
            model_name="emailtemplate",
            constraint=models.UniqueConstraint(
                fields=("organization", "template_key"),
                name="uniq_email_template_org_key",
            ),
        ),
        migrations.AddConstraint(
            model_name="emailtemplateversion",
            constraint=models.UniqueConstraint(
                fields=("template", "version_number"),
                name="uniq_email_template_version",
            ),
        ),
        migrations.AddIndex(
            model_name="emailtemplate",
            index=models.Index(
                fields=["organization", "status", "signal"],
                name="email_tpl_org_signal_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="emailtemplate",
            index=models.Index(
                fields=["legal_entity", "status"],
                name="email_tpl_entity_status_idx",
            ),
        ),
    ]
