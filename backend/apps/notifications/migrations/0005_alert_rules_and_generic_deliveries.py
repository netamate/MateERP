import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.notifications.models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0004_direct_email_notifications"),
        ("operations", "0005_payg_billing_reconciliation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="kind",
            field=models.CharField(
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
            ),
        ),
        migrations.CreateModel(
            name="AlertRule",
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
                ("name", models.CharField(max_length=180)),
                (
                    "signal",
                    models.CharField(
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
                    ),
                ),
                ("enabled", models.BooleanField(default=True)),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("INFO", "Info"),
                            ("WARNING", "Warning"),
                            ("CRITICAL", "Critical"),
                        ],
                        default="WARNING",
                        max_length=16,
                    ),
                ),
                (
                    "frequency",
                    models.CharField(
                        choices=[("HOURLY", "Hourly"), ("DAILY", "Daily")],
                        default="DAILY",
                        max_length=16,
                    ),
                ),
                ("schedule_hour", models.PositiveSmallIntegerField(default=8)),
                ("schedule_timezone", models.CharField(default="UTC", max_length=64)),
                ("in_app_enabled", models.BooleanField(default=True)),
                ("email_enabled", models.BooleanField(default=False)),
                ("hermes_enabled", models.BooleanField(default=False)),
                ("recipient_user_ids", models.JSONField(blank=True, default=list)),
                ("email_recipients", models.JSONField(blank=True, default=list)),
                ("hermes_target", models.CharField(blank=True, max_length=180)),
                (
                    "renewal_days",
                    models.JSONField(default=apps.notifications.models.default_renewal_days),
                ),
                ("grace_days", models.PositiveSmallIntegerField(default=1)),
                ("respect_subscription_channels", models.BooleanField(default=False)),
                ("last_evaluated_at", models.DateTimeField(blank=True, null=True)),
                ("last_delivery_count", models.PositiveIntegerField(default=0)),
                ("last_failure_count", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_alert_rules",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "legal_entity",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alert_rules",
                        to="identity.legalentity",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="alert_rules",
                        to="identity.organization",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_alert_rules",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["signal", "legal_entity_id", "name"]},
        ),
        migrations.AlterField(
            model_name="notificationdelivery",
            name="subscription",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="notification_deliveries",
                to="operations.subscription",
            ),
        ),
        migrations.AlterField(
            model_name="notificationdelivery",
            name="reminder_days_before",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="notificationdelivery",
            name="due_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notificationdelivery",
            name="alert_rule",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="deliveries",
                to="notifications.alertrule",
            ),
        ),
        migrations.AddField(
            model_name="notificationdelivery",
            name="signal",
            field=models.CharField(
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
                default="RENEWAL_DUE",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="notificationdelivery",
            name="source_type",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="notificationdelivery",
            name="source_id",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="notificationdelivery",
            name="severity",
            field=models.CharField(
                choices=[
                    ("INFO", "Info"),
                    ("WARNING", "Warning"),
                    ("CRITICAL", "Critical"),
                ],
                default="INFO",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="notificationdelivery",
            name="link",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="notificationdelivery",
            name="context",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddConstraint(
            model_name="alertrule",
            constraint=models.UniqueConstraint(
                fields=("organization", "legal_entity", "signal"),
                name="uniq_alert_rule_scope_signal",
                nulls_distinct=False,
            ),
        ),
        migrations.AddIndex(
            model_name="alertrule",
            index=models.Index(
                fields=["organization", "enabled", "signal"],
                name="alert_rule_org_signal_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="alertrule",
            index=models.Index(
                fields=["legal_entity", "enabled", "signal"],
                name="alert_rule_entity_signal_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notificationdelivery",
            index=models.Index(
                fields=["alert_rule", "signal", "status"],
                name="delivery_rule_signal_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notificationdelivery",
            index=models.Index(
                fields=["legal_entity", "signal", "created_at"],
                name="delivery_entity_signal_idx",
            ),
        ),
    ]
