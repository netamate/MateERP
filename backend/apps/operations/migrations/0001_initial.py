import decimal
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounting", "0001_initial"),
        ("finance", "0001_initial"),
        ("identity", "0001_initial"),
        ("planning", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Domain",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("domain_name", models.CharField(max_length=253)),
                ("registrar", models.CharField(blank=True, max_length=180)),
                ("dns_provider", models.CharField(blank=True, max_length=180)),
                ("purpose", models.CharField(blank=True, max_length=255)),
                ("purchase_date", models.DateField(blank=True, null=True)),
                ("expiry_date", models.DateField()),
                (
                    "renewal_amount",
                    models.DecimalField(decimal_places=2, default=decimal.Decimal("0"), max_digits=20),
                ),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("auto_renew", models.BooleanField(default=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("ACTIVE", "Active"), ("ARCHIVED", "Archived")],
                        default="ACTIVE",
                        max_length=16,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "expense_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="domain_expenses",
                        to="accounting.account",
                    ),
                ),
                (
                    "legal_entity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="domains",
                        to="identity.legalentity",
                    ),
                ),
                (
                    "payable_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="domain_payables",
                        to="accounting.account",
                    ),
                ),
                (
                    "payment_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="domains",
                        to="finance.financialaccount",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="domains",
                        to="planning.product",
                    ),
                ),
            ],
            options={
                "ordering": ["expiry_date", "domain_name"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("legal_entity", "domain_name"),
                        name="uniq_domain_name_per_entity",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="InfrastructureAsset",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                (
                    "asset_type",
                    models.CharField(
                        choices=[
                            ("VPS", "VPS"),
                            ("HOSTING", "Hosting"),
                            ("CLOUD", "Cloud"),
                            ("STORAGE", "Storage"),
                            ("CDN", "CDN"),
                            ("BACKUP", "Backup"),
                            ("EMAIL", "Email Infrastructure"),
                            ("MONITORING", "Monitoring"),
                            ("OTHER", "Other"),
                        ],
                        max_length=20,
                    ),
                ),
                ("provider_reference", models.CharField(blank=True, max_length=180)),
                ("purpose", models.CharField(blank=True, max_length=255)),
                ("started_on", models.DateField(blank=True, null=True)),
                ("next_renewal_date", models.DateField(blank=True, null=True)),
                (
                    "renewal_amount",
                    models.DecimalField(decimal_places=2, default=decimal.Decimal("0"), max_digits=20),
                ),
                ("currency", models.CharField(default="USD", max_length=3)),
                (
                    "billing_cycle",
                    models.CharField(
                        choices=[
                            ("MONTHLY", "Monthly"),
                            ("QUARTERLY", "Quarterly"),
                            ("SEMIANNUAL", "Semiannual"),
                            ("ANNUAL", "Annual"),
                            ("CUSTOM", "Custom"),
                        ],
                        default="MONTHLY",
                        max_length=16,
                    ),
                ),
                ("auto_renew", models.BooleanField(default=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("ACTIVE", "Active"), ("ARCHIVED", "Archived")],
                        default="ACTIVE",
                        max_length=16,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "cost_center",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="infrastructure_assets",
                        to="planning.costcenter",
                    ),
                ),
                (
                    "expense_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="infrastructure_expenses",
                        to="accounting.account",
                    ),
                ),
                (
                    "legal_entity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="infrastructure_assets",
                        to="identity.legalentity",
                    ),
                ),
                (
                    "payable_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="infrastructure_payables",
                        to="accounting.account",
                    ),
                ),
                (
                    "payment_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="infrastructure_assets",
                        to="finance.financialaccount",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="infrastructure_assets",
                        to="planning.product",
                    ),
                ),
                (
                    "vendor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="infrastructure_assets",
                        to="finance.vendor",
                    ),
                ),
            ],
            options={
                "ordering": ["next_renewal_date", "name"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("legal_entity", "name"),
                        name="uniq_infrastructure_name_per_entity",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("category", models.CharField(blank=True, max_length=120)),
                ("description", models.TextField(blank=True)),
                (
                    "amount",
                    models.DecimalField(decimal_places=2, default=decimal.Decimal("0"), max_digits=20),
                ),
                ("currency", models.CharField(default="USD", max_length=3)),
                (
                    "billing_cycle",
                    models.CharField(
                        choices=[
                            ("MONTHLY", "Monthly"),
                            ("QUARTERLY", "Quarterly"),
                            ("SEMIANNUAL", "Semiannual"),
                            ("ANNUAL", "Annual"),
                            ("CUSTOM", "Custom"),
                        ],
                        default="MONTHLY",
                        max_length=16,
                    ),
                ),
                ("started_on", models.DateField(blank=True, null=True)),
                ("next_renewal_date", models.DateField(blank=True, null=True)),
                ("auto_renew", models.BooleanField(default=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("ACTIVE", "Active"), ("ARCHIVED", "Archived")],
                        default="ACTIVE",
                        max_length=16,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "cost_center",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="planning.costcenter",
                    ),
                ),
                (
                    "expense_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="operational_subscriptions",
                        to="accounting.account",
                    ),
                ),
                (
                    "legal_entity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="identity.legalentity",
                    ),
                ),
                (
                    "payable_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscription_payables",
                        to="accounting.account",
                    ),
                ),
                (
                    "payment_account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="finance.financialaccount",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="planning.product",
                    ),
                ),
                (
                    "vendor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="finance.vendor",
                    ),
                ),
            ],
            options={
                "ordering": ["next_renewal_date", "name"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("legal_entity", "name"),
                        name="uniq_subscription_name_per_entity",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="DomainRenewal",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("renewed_on", models.DateField()),
                ("previous_expiry_date", models.DateField()),
                ("new_expiry_date", models.DateField()),
                ("amount", models.DecimalField(decimal_places=2, max_digits=20)),
                ("currency", models.CharField(max_length=3)),
                (
                    "fx_rate",
                    models.DecimalField(decimal_places=10, default=decimal.Decimal("1"), max_digits=20),
                ),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="recorded_domain_renewals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "domain",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="renewal_history",
                        to="operations.domain",
                    ),
                ),
                (
                    "expense",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="domain_renewal",
                        to="finance.expense",
                    ),
                ),
                (
                    "legal_entity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="domain_renewals",
                        to="identity.legalentity",
                    ),
                ),
            ],
            options={"ordering": ["-renewed_on", "-created_at"]},
        ),
    ]
