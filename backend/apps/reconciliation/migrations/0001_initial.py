import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounting", "0001_initial"),
        ("finance", "0001_initial"),
        ("identity", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountReconciliation",
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
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                (
                    "statement_ending_balance",
                    models.DecimalField(decimal_places=2, max_digits=20),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("DRAFT", "Draft"), ("COMPLETED", "Completed")],
                        default="DRAFT",
                        max_length=16,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "completed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="completed_reconciliations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_reconciliations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "financial_account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reconciliations",
                        to="finance.financialaccount",
                    ),
                ),
                (
                    "legal_entity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="account_reconciliations",
                        to="identity.legalentity",
                    ),
                ),
            ],
            options={"ordering": ["-end_date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="ReconciliationItem",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "journal_line",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reconciliation_item",
                        to="accounting.journalline",
                    ),
                ),
                (
                    "reconciliation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="reconciliation.accountreconciliation",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.AddConstraint(
            model_name="accountreconciliation",
            constraint=models.UniqueConstraint(
                fields=("financial_account", "start_date", "end_date"),
                name="uniq_reconciliation_period_per_account",
            ),
        ),
        migrations.AddIndex(
            model_name="accountreconciliation",
            index=models.Index(
                fields=["legal_entity", "status", "end_date"],
                name="recon_entity_status_idx",
            ),
        ),
    ]
