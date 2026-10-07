import decimal
import uuid

import django.db.models.deletion
from django.db import migrations, models

import apps.operations.models


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0002_document_library"),
        ("operations", "0004_vendor_service_accounts"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="billing_mode",
            field=models.CharField(
                choices=[("FIXED", "Fixed"), ("PAYG", "Pay as you go")],
                default="FIXED",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="subscription",
            name="estimated_cost",
            field=models.DecimalField(
                decimal_places=2,
                default=decimal.Decimal("0"),
                max_digits=20,
            ),
        ),
        migrations.AddField(
            model_name="subscription",
            name="monthly_budget",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="subscription",
            name="budget_alert_thresholds",
            field=models.JSONField(
                default=apps.operations.models.default_budget_alert_thresholds
            ),
        ),
        migrations.AddField(
            model_name="subscription",
            name="usage_unit",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.CreateModel(
            name="SubscriptionBillingPeriod",
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
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                (
                    "estimated_cost",
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal("0"),
                        max_digits=20,
                    ),
                ),
                (
                    "current_usage_amount",
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal("0"),
                        max_digits=20,
                    ),
                ),
                (
                    "usage_quantity",
                    models.DecimalField(
                        blank=True,
                        decimal_places=4,
                        max_digits=20,
                        null=True,
                    ),
                ),
                ("usage_unit", models.CharField(blank=True, max_length=40)),
                (
                    "current_usage_updated_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("is_closed", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_subscription_billing_periods",
                        to="identity.user",
                    ),
                ),
                (
                    "legal_entity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscription_billing_periods",
                        to="identity.legalentity",
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="billing_periods",
                        to="operations.subscription",
                    ),
                ),
            ],
            options={"ordering": ["-period_end", "-created_at"]},
        ),
        migrations.CreateModel(
            name="SubscriptionInvoice",
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
                ("invoice_number", models.CharField(max_length=180)),
                ("invoice_date", models.DateField()),
                ("due_date", models.DateField(blank=True, null=True)),
                ("currency", models.CharField(max_length=3)),
                ("subtotal", models.DecimalField(decimal_places=2, max_digits=20)),
                (
                    "tax_amount",
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal("0"),
                        max_digits=20,
                    ),
                ),
                ("total_amount", models.DecimalField(decimal_places=2, max_digits=20)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("OPEN", "Open"),
                            ("PARTIALLY_PAID", "Partially paid"),
                            ("PAID", "Paid"),
                            ("VOID", "Void"),
                        ],
                        default="OPEN",
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "billing_period",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="invoices",
                        to="operations.subscriptionbillingperiod",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_subscription_invoices",
                        to="identity.user",
                    ),
                ),
                (
                    "document",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscription_invoice",
                        to="finance.financedocument",
                    ),
                ),
                (
                    "expense",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscription_invoice",
                        to="finance.expense",
                    ),
                ),
                (
                    "legal_entity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscription_invoices",
                        to="identity.legalentity",
                    ),
                ),
                (
                    "vendor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscription_invoices",
                        to="finance.vendor",
                    ),
                ),
            ],
            options={"ordering": ["-invoice_date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="BillingPayment",
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
                    "payment_code",
                    models.CharField(editable=False, max_length=20, unique=True),
                ),
                ("paid_on", models.DateField()),
                ("amount", models.DecimalField(decimal_places=2, max_digits=20)),
                ("currency", models.CharField(max_length=3)),
                ("reference", models.CharField(blank=True, max_length=180)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_billing_payments",
                        to="identity.user",
                    ),
                ),
                (
                    "expense_payment",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="billing_payment",
                        to="finance.expensepayment",
                    ),
                ),
                (
                    "financial_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="billing_payments",
                        to="finance.financialaccount",
                    ),
                ),
                (
                    "legal_entity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="billing_payments",
                        to="identity.legalentity",
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="billing_payments",
                        to="operations.subscription",
                    ),
                ),
            ],
            options={"ordering": ["-paid_on", "-created_at"]},
        ),
        migrations.CreateModel(
            name="BillingPaymentAllocation",
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
                ("amount", models.DecimalField(decimal_places=2, max_digits=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payment_allocations",
                        to="operations.subscriptioninvoice",
                    ),
                ),
                (
                    "payment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="allocations",
                        to="operations.billingpayment",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.AddConstraint(
            model_name="subscriptionbillingperiod",
            constraint=models.UniqueConstraint(
                fields=("subscription", "period_start", "period_end"),
                name="uniq_subscription_billing_period",
            ),
        ),
        migrations.AddIndex(
            model_name="subscriptionbillingperiod",
            index=models.Index(
                fields=["legal_entity", "period_end"],
                name="billing_period_entity_end_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="subscriptioninvoice",
            constraint=models.UniqueConstraint(
                models.functions.Lower("invoice_number"),
                "vendor",
                name="uniq_billing_invoice_vendor_number_ci",
            ),
        ),
        migrations.AddIndex(
            model_name="subscriptioninvoice",
            index=models.Index(
                fields=["legal_entity", "status", "invoice_date"],
                name="billing_invoice_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="billingpayment",
            index=models.Index(
                fields=["legal_entity", "paid_on"],
                name="billing_payment_entity_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="billingpaymentallocation",
            constraint=models.UniqueConstraint(
                fields=("payment", "invoice"),
                name="uniq_billing_payment_invoice_allocation",
            ),
        ),
    ]
