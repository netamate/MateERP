import decimal
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
            name="Account",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=32)),
                ("name", models.CharField(max_length=180)),
                ("account_type", models.CharField(choices=[("ASSET", "Asset"), ("LIABILITY", "Liability"), ("EQUITY", "Equity"), ("REVENUE", "Revenue"), ("EXPENSE", "Expense")], max_length=16)),
                ("normal_balance", models.CharField(choices=[("DEBIT", "Debit"), ("CREDIT", "Credit")], max_length=8)),
                ("system_code", models.CharField(blank=True, max_length=64)),
                ("is_control", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("legal_entity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="accounts", to="identity.legalentity")),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="children", to="accounting.account")),
            ],
            options={"ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="FiscalPeriod",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=80)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("SOFT_CLOSED", "Soft closed"), ("HARD_CLOSED", "Hard closed")], default="OPEN", max_length=16)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("closed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="closed_fiscal_periods", to=settings.AUTH_USER_MODEL)),
                ("legal_entity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fiscal_periods", to="identity.legalentity")),
            ],
            options={"ordering": ["start_date"]},
        ),
        migrations.CreateModel(
            name="ExchangeRate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("rate_date", models.DateField()),
                ("from_currency", models.CharField(max_length=3)),
                ("to_currency", models.CharField(max_length=3)),
                ("rate", models.DecimalField(decimal_places=10, max_digits=20)),
                ("source", models.CharField(blank=True, max_length=80)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("legal_entity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="exchange_rates", to="identity.legalentity")),
            ],
            options={"ordering": ["-rate_date", "from_currency"]},
        ),
        migrations.CreateModel(
            name="JournalEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("number", models.CharField(max_length=32)),
                ("entry_date", models.DateField()),
                ("memo", models.CharField(blank=True, max_length=255)),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("POSTED", "Posted"), ("REVERSED", "Reversed")], default="DRAFT", max_length=16)),
                ("source_type", models.CharField(default="MANUAL", max_length=48)),
                ("source_id", models.CharField(blank=True, max_length=64)),
                ("posted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_journal_entries", to=settings.AUTH_USER_MODEL)),
                ("legal_entity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journal_entries", to="identity.legalentity")),
                ("posted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="posted_journal_entries", to=settings.AUTH_USER_MODEL)),
                ("reversal_of", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reversal_entry", to="accounting.journalentry")),
            ],
            options={"ordering": ["-entry_date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="JournalSequence",
            fields=[
                ("legal_entity", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, primary_key=True, related_name="journal_sequence", serialize=False, to="identity.legalentity")),
                ("next_number", models.PositiveBigIntegerField(default=1)),
            ],
        ),
        migrations.CreateModel(
            name="TaxCode",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=32)),
                ("name", models.CharField(max_length=120)),
                ("rate", models.DecimalField(decimal_places=6, default=decimal.Decimal("0"), max_digits=9)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("input_account", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="input_tax_codes", to="accounting.account")),
                ("legal_entity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tax_codes", to="identity.legalentity")),
                ("output_account", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="output_tax_codes", to="accounting.account")),
            ],
            options={"ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="JournalLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("debit", models.DecimalField(decimal_places=2, default=decimal.Decimal("0"), max_digits=20)),
                ("credit", models.DecimalField(decimal_places=2, default=decimal.Decimal("0"), max_digits=20)),
                ("currency", models.CharField(max_length=3)),
                ("fx_rate", models.DecimalField(decimal_places=10, default=decimal.Decimal("1"), max_digits=20)),
                ("base_debit", models.DecimalField(decimal_places=2, default=decimal.Decimal("0"), max_digits=20)),
                ("base_credit", models.DecimalField(decimal_places=2, default=decimal.Decimal("0"), max_digits=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journal_lines", to="accounting.account")),
                ("journal_entry", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lines", to="accounting.journalentry")),
                ("tax_code", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="journal_lines", to="accounting.taxcode")),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.AddConstraint(model_name="account", constraint=models.UniqueConstraint(fields=("legal_entity", "code"), name="uniq_account_code_per_entity")),
        migrations.AddConstraint(model_name="account", constraint=models.UniqueConstraint(condition=models.Q(("system_code", ""), _negated=True), fields=("legal_entity", "system_code"), name="uniq_account_system_code_per_entity")),
        migrations.AddConstraint(model_name="fiscalperiod", constraint=models.UniqueConstraint(fields=("legal_entity", "start_date", "end_date"), name="uniq_fiscal_period_dates_per_entity")),
        migrations.AddConstraint(model_name="exchangerate", constraint=models.UniqueConstraint(fields=("legal_entity", "rate_date", "from_currency", "to_currency"), name="uniq_fx_rate_per_entity_date_pair")),
        migrations.AddConstraint(model_name="journalentry", constraint=models.UniqueConstraint(fields=("legal_entity", "number"), name="uniq_journal_number_per_entity")),
        migrations.AddConstraint(model_name="taxcode", constraint=models.UniqueConstraint(fields=("legal_entity", "code"), name="uniq_tax_code_per_entity")),
    ]
