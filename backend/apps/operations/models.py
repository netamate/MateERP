import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.accounting.models import Account, AccountType
from apps.finance.models import Expense, FinancialAccount, Vendor
from apps.identity.models import LegalEntity
from apps.planning.models import CostCenter, Product


class OperationalStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    ARCHIVED = "ARCHIVED", "Archived"


class BillingCycle(models.TextChoices):
    MONTHLY = "MONTHLY", "Monthly"
    QUARTERLY = "QUARTERLY", "Quarterly"
    SEMIANNUAL = "SEMIANNUAL", "Semiannual"
    ANNUAL = "ANNUAL", "Annual"
    CUSTOM = "CUSTOM", "Custom"


class ServiceType(models.TextChoices):
    DOMAIN = "DOMAIN", "Domain"
    VPS = "VPS", "VPS / Server"
    CLOUD = "CLOUD", "Cloud"
    HOSTING = "HOSTING", "Hosting"
    SAAS = "SAAS", "SaaS / Software"
    API = "API", "API / Usage Service"
    STORAGE = "STORAGE", "Storage / Backup"
    EMAIL = "EMAIL", "Email Service"
    AI = "AI", "AI Service"
    OTHER = "OTHER", "Other"


class InfrastructureType(models.TextChoices):
    VPS = "VPS", "VPS"
    HOSTING = "HOSTING", "Hosting"
    CLOUD = "CLOUD", "Cloud"
    STORAGE = "STORAGE", "Storage"
    CDN = "CDN", "CDN"
    BACKUP = "BACKUP", "Backup"
    EMAIL = "EMAIL", "Email Infrastructure"
    MONITORING = "MONITORING", "Monitoring"
    OTHER = "OTHER", "Other"


def _validate_scoped_reference(legal_entity_id, obj, label: str) -> None:
    if obj and obj.legal_entity_id != legal_entity_id:
        raise ValidationError(f"{label} must belong to the same legal entity.")


def _validate_expense_accounts(legal_entity_id, expense_account, payable_account) -> None:
    _validate_scoped_reference(legal_entity_id, expense_account, "Expense account")
    _validate_scoped_reference(legal_entity_id, payable_account, "Payable account")
    if expense_account and expense_account.account_type != AccountType.EXPENSE:
        raise ValidationError("Expense account must be an expense account.")
    if payable_account and payable_account.account_type != AccountType.LIABILITY:
        raise ValidationError("Payable account must be a liability account.")


class Subscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=180)
    service_type = models.CharField(
        max_length=20,
        choices=ServiceType.choices,
        default=ServiceType.OTHER,
    )
    description = models.TextField(blank=True)
    reference = models.CharField(max_length=255, blank=True)
    payment_method = models.CharField(max_length=180, blank=True)
    amount = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=3, default="USD")
    billing_cycle = models.CharField(
        max_length=16,
        choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY,
    )
    started_on = models.DateField(null=True, blank=True)
    next_renewal_date = models.DateField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True)
    status = models.CharField(
        max_length=16,
        choices=OperationalStatus.choices,
        default=OperationalStatus.ACTIVE,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["next_renewal_date", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["legal_entity", "name"],
                name="uniq_subscription_name_per_entity",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.currency = self.currency.upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.amount < 0:
            raise ValidationError("Subscription amount cannot be negative.")
        if self.started_on and self.next_renewal_date and self.next_renewal_date < self.started_on:
            raise ValidationError("Next renewal cannot be before the subscription start date.")
        _validate_scoped_reference(self.legal_entity_id, self.vendor, "Vendor")


class Domain(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="domains",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="domains",
        null=True,
        blank=True,
    )
    payment_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="domains",
        null=True,
        blank=True,
    )
    expense_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="domain_expenses",
        null=True,
        blank=True,
    )
    payable_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="domain_payables",
        null=True,
        blank=True,
    )
    domain_name = models.CharField(max_length=253)
    registrar = models.CharField(max_length=180, blank=True)
    dns_provider = models.CharField(max_length=180, blank=True)
    purpose = models.CharField(max_length=255, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField()
    renewal_amount = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=3, default="USD")
    auto_renew = models.BooleanField(default=True)
    status = models.CharField(
        max_length=16,
        choices=OperationalStatus.choices,
        default=OperationalStatus.ACTIVE,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["expiry_date", "domain_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["legal_entity", "domain_name"],
                name="uniq_domain_name_per_entity",
            )
        ]

    def __str__(self) -> str:
        return self.domain_name

    def save(self, *args, **kwargs):
        self.domain_name = self.domain_name.lower().strip()
        self.currency = self.currency.upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.renewal_amount < 0:
            raise ValidationError("Domain renewal amount cannot be negative.")
        if self.purchase_date and self.expiry_date < self.purchase_date:
            raise ValidationError("Domain expiry cannot be before purchase date.")
        for obj, label in ((self.product, "Product"), (self.payment_account, "Payment account")):
            _validate_scoped_reference(self.legal_entity_id, obj, label)
        _validate_expense_accounts(self.legal_entity_id, self.expense_account, self.payable_account)


class InfrastructureAsset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="infrastructure_assets",
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="infrastructure_assets",
        null=True,
        blank=True,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="infrastructure_assets",
        null=True,
        blank=True,
    )
    cost_center = models.ForeignKey(
        CostCenter,
        on_delete=models.PROTECT,
        related_name="infrastructure_assets",
        null=True,
        blank=True,
    )
    payment_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="infrastructure_assets",
        null=True,
        blank=True,
    )
    expense_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="infrastructure_expenses",
        null=True,
        blank=True,
    )
    payable_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="infrastructure_payables",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=180)
    asset_type = models.CharField(max_length=20, choices=InfrastructureType.choices)
    provider_reference = models.CharField(max_length=180, blank=True)
    purpose = models.CharField(max_length=255, blank=True)
    started_on = models.DateField(null=True, blank=True)
    next_renewal_date = models.DateField(null=True, blank=True)
    renewal_amount = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=3, default="USD")
    billing_cycle = models.CharField(
        max_length=16,
        choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY,
    )
    auto_renew = models.BooleanField(default=True)
    status = models.CharField(
        max_length=16,
        choices=OperationalStatus.choices,
        default=OperationalStatus.ACTIVE,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["next_renewal_date", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["legal_entity", "name"],
                name="uniq_infrastructure_name_per_entity",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.currency = self.currency.upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.renewal_amount < 0:
            raise ValidationError("Infrastructure renewal amount cannot be negative.")
        if self.started_on and self.next_renewal_date and self.next_renewal_date < self.started_on:
            raise ValidationError("Next renewal cannot be before the infrastructure start date.")
        for obj, label in (
            (self.vendor, "Vendor"),
            (self.product, "Product"),
            (self.cost_center, "Cost center"),
            (self.payment_account, "Payment account"),
        ):
            _validate_scoped_reference(self.legal_entity_id, obj, label)
        _validate_expense_accounts(self.legal_entity_id, self.expense_account, self.payable_account)


class DomainRenewal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="domain_renewals",
    )
    domain = models.ForeignKey(
        Domain,
        on_delete=models.PROTECT,
        related_name="renewal_history",
    )
    expense = models.OneToOneField(
        Expense,
        on_delete=models.PROTECT,
        related_name="domain_renewal",
        null=True,
        blank=True,
    )
    renewed_on = models.DateField()
    previous_expiry_date = models.DateField()
    new_expiry_date = models.DateField()
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=3)
    fx_rate = models.DecimalField(max_digits=20, decimal_places=10, default=Decimal("1"))
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_domain_renewals",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-renewed_on", "-created_at"]

    def __str__(self) -> str:
        return f"{self.domain.domain_name} renewal {self.new_expiry_date}"

    def save(self, *args, **kwargs):
        self.currency = self.currency.upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.amount < 0 or self.fx_rate <= 0:
            raise ValidationError("Renewal amount cannot be negative and FX rate must be positive.")
        if self.new_expiry_date <= self.previous_expiry_date:
            raise ValidationError("New domain expiry must be after the previous expiry date.")
        _validate_scoped_reference(self.legal_entity_id, self.domain, "Domain")
        _validate_scoped_reference(self.legal_entity_id, self.expense, "Expense")
