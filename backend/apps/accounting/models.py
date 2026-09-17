import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.identity.models import LegalEntity


class AccountType(models.TextChoices):
    ASSET = "ASSET", "Asset"
    LIABILITY = "LIABILITY", "Liability"
    EQUITY = "EQUITY", "Equity"
    REVENUE = "REVENUE", "Revenue"
    EXPENSE = "EXPENSE", "Expense"


class NormalBalance(models.TextChoices):
    DEBIT = "DEBIT", "Debit"
    CREDIT = "CREDIT", "Credit"


class JournalStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    POSTED = "POSTED", "Posted"
    REVERSED = "REVERSED", "Reversed"


class PeriodStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    SOFT_CLOSED = "SOFT_CLOSED", "Soft closed"
    HARD_CLOSED = "HARD_CLOSED", "Hard closed"


class Account(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="accounts",
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=180)
    account_type = models.CharField(max_length=16, choices=AccountType.choices)
    normal_balance = models.CharField(max_length=8, choices=NormalBalance.choices)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )
    system_code = models.CharField(max_length=64, blank=True)
    is_control = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["legal_entity", "code"],
                name="uniq_account_code_per_entity",
            ),
            models.UniqueConstraint(
                fields=["legal_entity", "system_code"],
                condition=~models.Q(system_code=""),
                name="uniq_account_system_code_per_entity",
            ),
        ]

    def clean(self):
        if self.parent_id and self.parent.legal_entity_id != self.legal_entity_id:
            raise ValidationError("Parent account must belong to the same legal entity.")
        if self.parent_id == self.id:
            raise ValidationError("An account cannot be its own parent.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class FiscalPeriod(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="fiscal_periods",
    )
    name = models.CharField(max_length=80)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=16,
        choices=PeriodStatus.choices,
        default=PeriodStatus.OPEN,
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="closed_fiscal_periods",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["legal_entity", "start_date", "end_date"],
                name="uniq_fiscal_period_dates_per_entity",
            )
        ]

    def clean(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("Fiscal period start date must be before end date.")
        if self.legal_entity_id and self.start_date and self.end_date:
            overlap = FiscalPeriod.objects.filter(
                legal_entity_id=self.legal_entity_id,
                start_date__lte=self.end_date,
                end_date__gte=self.start_date,
            ).exclude(pk=self.pk)
            if overlap.exists():
                raise ValidationError("Fiscal periods cannot overlap.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class TaxCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="tax_codes",
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=120)
    rate = models.DecimalField(max_digits=9, decimal_places=6, default=Decimal("0"))
    input_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="input_tax_codes",
        null=True,
        blank=True,
    )
    output_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="output_tax_codes",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["legal_entity", "code"],
                name="uniq_tax_code_per_entity",
            )
        ]

    def clean(self):
        for account in (self.input_account, self.output_account):
            if account and account.legal_entity_id != self.legal_entity_id:
                raise ValidationError("Tax accounts must belong to the same legal entity.")

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        self.full_clean()
        super().save(*args, **kwargs)


class ExchangeRate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="exchange_rates",
    )
    rate_date = models.DateField()
    from_currency = models.CharField(max_length=3)
    to_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=20, decimal_places=10)
    source = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-rate_date", "from_currency"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "legal_entity",
                    "rate_date",
                    "from_currency",
                    "to_currency",
                ],
                name="uniq_fx_rate_per_entity_date_pair",
            )
        ]

    def clean(self):
        if self.rate <= 0:
            raise ValidationError("Exchange rate must be greater than zero.")
        if self.from_currency.upper() == self.to_currency.upper():
            raise ValidationError("Exchange rate currencies must be different.")

    def save(self, *args, **kwargs):
        self.from_currency = self.from_currency.upper()
        self.to_currency = self.to_currency.upper()
        self.full_clean()
        super().save(*args, **kwargs)


class JournalSequence(models.Model):
    legal_entity = models.OneToOneField(
        LegalEntity,
        on_delete=models.PROTECT,
        primary_key=True,
        related_name="journal_sequence",
    )
    next_number = models.PositiveBigIntegerField(default=1)


class JournalEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="journal_entries",
    )
    number = models.CharField(max_length=32)
    entry_date = models.DateField()
    memo = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=16,
        choices=JournalStatus.choices,
        default=JournalStatus.DRAFT,
    )
    source_type = models.CharField(max_length=48, default="MANUAL")
    source_id = models.CharField(max_length=64, blank=True)
    reversal_of = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        related_name="reversal_entry",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_journal_entries",
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="posted_journal_entries",
        null=True,
        blank=True,
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-entry_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["legal_entity", "number"],
                name="uniq_journal_number_per_entity",
            )
        ]

    def delete(self, *args, **kwargs):
        if self.status != JournalStatus.DRAFT:
            raise ValidationError("Posted or reversed journal entries cannot be deleted.")
        return super().delete(*args, **kwargs)


class JournalLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="lines",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="journal_lines",
    )
    description = models.CharField(max_length=255, blank=True)
    debit = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    credit = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=3)
    fx_rate = models.DecimalField(max_digits=20, decimal_places=10, default=Decimal("1"))
    base_debit = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    base_credit = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    tax_code = models.ForeignKey(
        TaxCode,
        on_delete=models.PROTECT,
        related_name="journal_lines",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def clean(self):
        if self.journal_entry_id and self.journal_entry.status != JournalStatus.DRAFT:
            raise ValidationError("Posted journal lines are immutable.")
        if self.account_id and self.journal_entry_id:
            if self.account.legal_entity_id != self.journal_entry.legal_entity_id:
                raise ValidationError("Account must belong to the journal legal entity.")
        if self.tax_code_id and self.journal_entry_id:
            if self.tax_code.legal_entity_id != self.journal_entry.legal_entity_id:
                raise ValidationError("Tax code must belong to the journal legal entity.")
        debit_positive = self.debit > 0
        credit_positive = self.credit > 0
        if debit_positive == credit_positive:
            raise ValidationError("Each journal line must contain one debit or one credit.")
        if self.debit < 0 or self.credit < 0:
            raise ValidationError("Debit and credit amounts cannot be negative.")
        if self.fx_rate <= 0:
            raise ValidationError("FX rate must be greater than zero.")

    def save(self, *args, **kwargs):
        self.currency = self.currency.upper()
        self.base_debit = (self.debit * self.fx_rate).quantize(Decimal("0.01"))
        self.base_credit = (self.credit * self.fx_rate).quantize(Decimal("0.01"))
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.journal_entry.status != JournalStatus.DRAFT:
            raise ValidationError("Posted journal lines are immutable.")
        return super().delete(*args, **kwargs)
