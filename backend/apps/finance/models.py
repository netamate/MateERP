import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.accounting.models import Account, AccountType, JournalEntry, TaxCode
from apps.identity.models import LegalEntity


class VendorStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class FinancialAccountType(models.TextChoices):
    BANK = "BANK", "Bank"
    CASH = "CASH", "Cash"
    CREDIT_CARD = "CREDIT_CARD", "Credit card"
    WALLET = "WALLET", "Wallet"
    PAYMENT_PROCESSOR = "PAYMENT_PROCESSOR", "Payment processor"


class ExpenseStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SUBMITTED = "SUBMITTED", "Submitted"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Partially paid"
    PAID = "PAID", "Paid"


class ReimbursementStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SUBMITTED = "SUBMITTED", "Submitted"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Partially paid"
    PAID = "PAID", "Paid"


class RecordStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    POSTED = "POSTED", "Posted"


class FounderFundingType(models.TextChoices):
    CONTRIBUTION = "CONTRIBUTION", "Founder contribution"
    LOAN = "LOAN", "Founder loan"


class DocumentType(models.TextChoices):
    RECEIPT = "RECEIPT", "Receipt"
    INVOICE = "INVOICE", "Invoice"
    BILL = "BILL", "Bill"
    STATEMENT = "STATEMENT", "Statement"
    PAYSLIP = "PAYSLIP", "Payslip"
    PAYMENT_CONFIRMATION = "PAYMENT_CONFIRMATION", "Payment confirmation"
    CREDIT_NOTE = "CREDIT_NOTE", "Credit note"
    OTHER = "OTHER", "Other"


def finance_document_upload_path(instance, filename: str) -> str:
    document_date = instance.document_date or timezone.localdate()
    stored_name = instance.standardized_name or filename
    return f"finance/{document_date.year}/{document_date.month:02d}/{stored_name}"


class ApprovalObjectType(models.TextChoices):
    EXPENSE = "EXPENSE", "Expense"
    REIMBURSEMENT = "REIMBURSEMENT", "Reimbursement"


class ApprovalActionType(models.TextChoices):
    SUBMITTED = "SUBMITTED", "Submitted"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


class Vendor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="vendors",
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=180)
    contact_name = models.CharField(max_length=160, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    tax_id = models.CharField(max_length=80, blank=True)
    payment_terms_days = models.PositiveSmallIntegerField(default=0)
    default_expense_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="default_for_vendors",
        null=True,
        blank=True,
    )
    payable_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="payable_for_vendors",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=16,
        choices=VendorStatus.choices,
        default=VendorStatus.ACTIVE,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["legal_entity", "code"],
                name="uniq_vendor_code_per_entity",
            )
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        for account in (self.default_expense_account, self.payable_account):
            if account and account.legal_entity_id != self.legal_entity_id:
                raise ValidationError("Vendor accounts must belong to the same legal entity.")
        if (
            self.default_expense_account
            and self.default_expense_account.account_type != AccountType.EXPENSE
        ):
            raise ValidationError("Default expense account must be an expense account.")
        if self.payable_account and self.payable_account.account_type != AccountType.LIABILITY:
            raise ValidationError("Vendor payable account must be a liability account.")


class FinancialAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="financial_accounts",
    )
    name = models.CharField(max_length=180)
    account_type = models.CharField(max_length=24, choices=FinancialAccountType.choices)
    currency = models.CharField(max_length=3)
    ledger_account = models.OneToOneField(
        Account,
        on_delete=models.PROTECT,
        related_name="financial_account",
    )
    institution_name = models.CharField(max_length=180, blank=True)
    last_four = models.CharField(max_length=4, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["legal_entity", "name"],
                name="uniq_financial_account_name_per_entity",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.currency = self.currency.upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.ledger_account_id and self.ledger_account.legal_entity_id != self.legal_entity_id:
            raise ValidationError("Ledger account must belong to the same legal entity.")
        if self.ledger_account_id:
            expected = (
                AccountType.LIABILITY
                if self.account_type == FinancialAccountType.CREDIT_CARD
                else AccountType.ASSET
            )
            if self.ledger_account.account_type != expected:
                raise ValidationError("Financial account ledger type does not match account type.")


class Expense(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="expenses",
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="expenses",
        null=True,
        blank=True,
    )
    expense_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    description = models.CharField(max_length=255)
    reference = models.CharField(max_length=120, blank=True)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=3)
    fx_rate = models.DecimalField(max_digits=20, decimal_places=10, default=Decimal("1"))
    expense_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="expenses",
    )
    payable_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="expense_payables",
    )
    tax_code = models.ForeignKey(
        TaxCode,
        on_delete=models.PROTECT,
        related_name="expenses",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=ExpenseStatus.choices,
        default=ExpenseStatus.DRAFT,
    )
    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="expense",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_expenses",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approved_expenses",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="rejected_expenses",
        null=True,
        blank=True,
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expense_date", "-created_at"]

    def __str__(self) -> str:
        return f"{self.expense_date} {self.description}"

    def save(self, *args, **kwargs):
        self.currency = self.currency.upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.amount <= 0:
            raise ValidationError("Expense amount must be greater than zero.")
        if self.tax_amount < 0 or self.tax_amount > self.amount:
            raise ValidationError("Tax amount must be between zero and the expense amount.")
        if self.fx_rate <= 0:
            raise ValidationError("FX rate must be greater than zero.")
        if self.vendor_id and self.vendor.legal_entity_id != self.legal_entity_id:
            raise ValidationError("Vendor must belong to the same legal entity.")
        for account in (self.expense_account, self.payable_account):
            if account and account.legal_entity_id != self.legal_entity_id:
                raise ValidationError("Expense accounts must belong to the same legal entity.")
        if self.expense_account_id and self.expense_account.account_type != AccountType.EXPENSE:
            raise ValidationError("Expense account must be an expense account.")
        if self.payable_account_id and self.payable_account.account_type != AccountType.LIABILITY:
            raise ValidationError("Payable account must be a liability account.")
        if self.tax_amount > 0 and not self.tax_code_id:
            raise ValidationError("A tax code is required when tax amount is greater than zero.")
        if self.tax_code_id:
            if self.tax_code.legal_entity_id != self.legal_entity_id:
                raise ValidationError("Tax code must belong to the same legal entity.")
            if self.tax_amount > 0 and not self.tax_code.input_account_id:
                raise ValidationError("Tax code requires an input account for expense tax.")


class ExpensePayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="expense_payments",
    )
    expense = models.ForeignKey(
        Expense,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    financial_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="expense_payments",
    )
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=3)
    fx_rate = models.DecimalField(max_digits=20, decimal_places=10, default=Decimal("1"))
    base_amount = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    reference = models.CharField(max_length=120, blank=True)
    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="expense_payment",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_expense_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]

    def __str__(self) -> str:
        return f"Payment {self.amount} {self.currency} for {self.expense_id}"

    def save(self, *args, **kwargs):
        self.currency = self.currency.upper()
        self.base_amount = (self.amount * self.fx_rate).quantize(Decimal("0.01"))
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.amount <= 0 or self.fx_rate <= 0:
            raise ValidationError("Payment amount and FX rate must be greater than zero.")
        if self.expense_id and self.expense.legal_entity_id != self.legal_entity_id:
            raise ValidationError("Expense must belong to the same legal entity.")
        if (
            self.financial_account_id
            and self.financial_account.legal_entity_id != self.legal_entity_id
        ):
            raise ValidationError("Financial account must belong to the same legal entity.")
        if self.financial_account_id and self.currency.upper() != self.financial_account.currency:
            raise ValidationError("Payment currency must match the financial account currency.")


class Income(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="income_records",
    )
    income_date = models.DateField()
    payer_name = models.CharField(max_length=180, blank=True)
    description = models.CharField(max_length=255)
    reference = models.CharField(max_length=120, blank=True)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=3)
    fx_rate = models.DecimalField(max_digits=20, decimal_places=10, default=Decimal("1"))
    revenue_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="income_records",
    )
    financial_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="income_records",
    )
    status = models.CharField(
        max_length=12,
        choices=RecordStatus.choices,
        default=RecordStatus.DRAFT,
    )
    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="income_record",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_income_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-income_date", "-created_at"]

    def __str__(self) -> str:
        return f"{self.income_date} {self.description}"

    def save(self, *args, **kwargs):
        self.currency = self.currency.upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.amount <= 0 or self.fx_rate <= 0:
            raise ValidationError("Income amount and FX rate must be greater than zero.")
        if self.revenue_account_id and self.revenue_account.legal_entity_id != self.legal_entity_id:
            raise ValidationError("Revenue account must belong to the same legal entity.")
        if self.revenue_account_id and self.revenue_account.account_type != AccountType.REVENUE:
            raise ValidationError("Revenue account must be a revenue account.")
        if (
            self.financial_account_id
            and self.financial_account.legal_entity_id != self.legal_entity_id
        ):
            raise ValidationError("Financial account must belong to the same legal entity.")
        if self.financial_account_id and self.currency.upper() != self.financial_account.currency:
            raise ValidationError("Income currency must match the financial account currency.")


class Transfer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="transfers",
    )
    transfer_date = models.DateField()
    from_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="outgoing_transfers",
    )
    to_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="incoming_transfers",
    )
    source_amount = models.DecimalField(max_digits=20, decimal_places=2)
    destination_amount = models.DecimalField(max_digits=20, decimal_places=2)
    source_fx_rate = models.DecimalField(max_digits=20, decimal_places=10, default=Decimal("1"))
    destination_fx_rate = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        default=Decimal("1"),
    )
    reference = models.CharField(max_length=120, blank=True)
    memo = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=12,
        choices=RecordStatus.choices,
        default=RecordStatus.DRAFT,
    )
    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="transfer",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_transfers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transfer_date", "-created_at"]

    def __str__(self) -> str:
        return f"Transfer {self.from_account_id} -> {self.to_account_id}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.from_account_id == self.to_account_id:
            raise ValidationError("Transfer accounts must be different.")
        for account in (self.from_account, self.to_account):
            if account and account.legal_entity_id != self.legal_entity_id:
                raise ValidationError("Transfer accounts must belong to the same legal entity.")
        if self.source_amount <= 0 or self.destination_amount <= 0:
            raise ValidationError("Transfer amounts must be greater than zero.")
        if self.source_fx_rate <= 0 or self.destination_fx_rate <= 0:
            raise ValidationError("Transfer FX rates must be greater than zero.")
        source_base = (self.source_amount * self.source_fx_rate).quantize(Decimal("0.01"))
        destination_base = (self.destination_amount * self.destination_fx_rate).quantize(
            Decimal("0.01")
        )
        if source_base != destination_base:
            raise ValidationError("Transfer must balance in base currency.")


class FounderFunding(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="founder_funding",
    )
    funding_date = models.DateField()
    founder_name = models.CharField(max_length=180)
    funding_type = models.CharField(max_length=16, choices=FounderFundingType.choices)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=3)
    fx_rate = models.DecimalField(max_digits=20, decimal_places=10, default=Decimal("1"))
    financial_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="founder_funding",
    )
    counter_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="founder_funding",
    )
    reference = models.CharField(max_length=120, blank=True)
    memo = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=12,
        choices=RecordStatus.choices,
        default=RecordStatus.DRAFT,
    )
    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="founder_funding",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_founder_funding",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-funding_date", "-created_at"]

    def __str__(self) -> str:
        return f"{self.founder_name} {self.funding_type} {self.amount}"

    def save(self, *args, **kwargs):
        self.currency = self.currency.upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.amount <= 0 or self.fx_rate <= 0:
            raise ValidationError("Funding amount and FX rate must be greater than zero.")
        if (
            self.financial_account_id
            and self.financial_account.legal_entity_id != self.legal_entity_id
        ):
            raise ValidationError("Financial account must belong to the same legal entity.")
        if self.counter_account_id and self.counter_account.legal_entity_id != self.legal_entity_id:
            raise ValidationError("Counter account must belong to the same legal entity.")
        if self.financial_account_id and self.currency.upper() != self.financial_account.currency:
            raise ValidationError("Funding currency must match the financial account currency.")
        expected = (
            AccountType.EQUITY
            if self.funding_type == FounderFundingType.CONTRIBUTION
            else AccountType.LIABILITY
        )
        if self.counter_account_id and self.counter_account.account_type != expected:
            raise ValidationError("Founder funding counter account has the wrong account type.")


class Reimbursement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="reimbursements",
    )
    claimant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reimbursements",
    )
    expense_date = models.DateField()
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=3)
    fx_rate = models.DecimalField(max_digits=20, decimal_places=10, default=Decimal("1"))
    expense_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="reimbursements",
    )
    payable_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="reimbursement_payables",
    )
    status = models.CharField(
        max_length=20,
        choices=ReimbursementStatus.choices,
        default=ReimbursementStatus.DRAFT,
    )
    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="reimbursement",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_reimbursements",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approved_reimbursements",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="rejected_reimbursements",
        null=True,
        blank=True,
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expense_date", "-created_at"]

    def __str__(self) -> str:
        return f"{self.claimant} {self.amount} {self.currency}"

    def save(self, *args, **kwargs):
        self.currency = self.currency.upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.amount <= 0 or self.fx_rate <= 0:
            raise ValidationError("Reimbursement amount and FX rate must be greater than zero.")
        for account in (self.expense_account, self.payable_account):
            if account and account.legal_entity_id != self.legal_entity_id:
                raise ValidationError(
                    "Reimbursement accounts must belong to the same legal entity."
                )
        if self.expense_account_id and self.expense_account.account_type != AccountType.EXPENSE:
            raise ValidationError("Reimbursement expense account must be an expense account.")
        if self.payable_account_id and self.payable_account.account_type != AccountType.LIABILITY:
            raise ValidationError("Reimbursement payable account must be a liability account.")


class ReimbursementPayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="reimbursement_payments",
    )
    reimbursement = models.ForeignKey(
        Reimbursement,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    financial_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="reimbursement_payments",
    )
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=3)
    fx_rate = models.DecimalField(max_digits=20, decimal_places=10, default=Decimal("1"))
    base_amount = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    reference = models.CharField(max_length=120, blank=True)
    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="reimbursement_payment",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_reimbursement_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]

    def __str__(self) -> str:
        return f"Reimbursement payment {self.amount} {self.currency}"

    def save(self, *args, **kwargs):
        self.currency = self.currency.upper()
        self.base_amount = (self.amount * self.fx_rate).quantize(Decimal("0.01"))
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.amount <= 0 or self.fx_rate <= 0:
            raise ValidationError("Payment amount and FX rate must be greater than zero.")
        if self.reimbursement_id and self.reimbursement.legal_entity_id != self.legal_entity_id:
            raise ValidationError("Reimbursement must belong to the same legal entity.")
        if (
            self.financial_account_id
            and self.financial_account.legal_entity_id != self.legal_entity_id
        ):
            raise ValidationError("Financial account must belong to the same legal entity.")
        if self.financial_account_id and self.currency.upper() != self.financial_account.currency:
            raise ValidationError("Payment currency must match the financial account currency.")


class ApprovalAction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="finance_approval_actions",
    )
    object_type = models.CharField(max_length=20, choices=ApprovalObjectType.choices)
    object_id = models.UUIDField()
    action = models.CharField(max_length=16, choices=ApprovalActionType.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="finance_approval_actions",
    )
    comment = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.object_type} {self.object_id}: {self.action}"


class FinanceDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="finance_documents",
    )
    document_type = models.CharField(max_length=24, choices=DocumentType.choices)
    document_date = models.DateField(default=timezone.localdate)
    reference = models.CharField(max_length=180, blank=True)
    file = models.FileField(upload_to=finance_document_upload_path)
    original_name = models.CharField(max_length=255)
    standardized_name = models.CharField(max_length=255, blank=True)
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="documents",
        null=True,
        blank=True,
    )
    service = models.ForeignKey(
        "operations.VendorService",
        on_delete=models.PROTECT,
        related_name="documents",
        null=True,
        blank=True,
    )
    service_account = models.ForeignKey(
        "operations.ServiceAccount",
        on_delete=models.PROTECT,
        related_name="documents",
        null=True,
        blank=True,
    )
    subscription = models.ForeignKey(
        "operations.Subscription",
        on_delete=models.PROTECT,
        related_name="documents",
        null=True,
        blank=True,
    )
    expense = models.ForeignKey(
        Expense,
        on_delete=models.PROTECT,
        related_name="documents",
        null=True,
        blank=True,
    )
    income = models.ForeignKey(
        Income,
        on_delete=models.PROTECT,
        related_name="documents",
        null=True,
        blank=True,
    )
    reimbursement = models.ForeignKey(
        Reimbursement,
        on_delete=models.PROTECT,
        related_name="documents",
        null=True,
        blank=True,
    )
    transfer = models.ForeignKey(
        Transfer,
        on_delete=models.PROTECT,
        related_name="documents",
        null=True,
        blank=True,
    )
    founder_funding = models.ForeignKey(
        FounderFunding,
        on_delete=models.PROTECT,
        related_name="documents",
        null=True,
        blank=True,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_finance_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-document_date", "-created_at"]
        indexes = [
            models.Index(
                fields=["legal_entity", "document_date"],
                name="finance_doc_date_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.standardized_name or self.original_name

    def save(self, *args, **kwargs):
        if self.subscription_id:
            if not self.vendor_id:
                self.vendor_id = self.subscription.vendor_id
            if not self.service_id:
                self.service_id = self.subscription.service_id
            if not self.service_account_id:
                self.service_account_id = self.subscription.service_account_id
        if self.service_account_id:
            if not self.service_id:
                self.service_id = self.service_account.service_id
            if not self.vendor_id:
                self.vendor_id = self.service_account.service.vendor_id
        if self.service_id and not self.vendor_id:
            self.vendor_id = self.service.vendor_id
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        finance_targets = [
            self.expense,
            self.income,
            self.reimbursement,
            self.transfer,
            self.founder_funding,
        ]
        if len([target for target in finance_targets if target is not None]) > 1:
            raise ValidationError(
                "A finance document can link to at most one transaction record."
            )
        scoped_records = [
            ("Vendor", self.vendor),
            ("Service", self.service),
            ("Service account", self.service_account),
            ("Subscription", self.subscription),
            ("Expense", self.expense),
            ("Income", self.income),
            ("Reimbursement", self.reimbursement),
            ("Transfer", self.transfer),
            ("Founder funding", self.founder_funding),
        ]
        for label, record in scoped_records:
            if record and record.legal_entity_id != self.legal_entity_id:
                raise ValidationError(f"{label} must belong to the same legal entity.")

        if self.service_id and self.vendor_id and self.service.vendor_id != self.vendor_id:
            raise ValidationError("Document service must belong to the selected vendor.")
        if (
            self.service_account_id
            and self.service_id
            and self.service_account.service_id != self.service_id
        ):
            raise ValidationError("Document account must belong to the selected service.")
        if self.subscription_id:
            if self.vendor_id and self.subscription.vendor_id != self.vendor_id:
                raise ValidationError("Document vendor must match the subscription vendor.")
            if self.service_id and self.subscription.service_id != self.service_id:
                raise ValidationError("Document service must match the subscription service.")
            if (
                self.service_account_id
                and self.subscription.service_account_id != self.service_account_id
            ):
                raise ValidationError("Document account must match the subscription account.")

