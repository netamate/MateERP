import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.finance.models import Vendor
from apps.identity.models import LegalEntity


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


def _validate_scoped_reference(legal_entity_id, obj, label: str) -> None:
    if obj and obj.legal_entity_id != legal_entity_id:
        raise ValidationError(f"{label} must belong to the same legal entity.")


class VendorService(models.Model):
    """Services offered by one vendor in one legal entity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity, on_delete=models.PROTECT, related_name="vendor_services"
    )
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="services")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=180)
    service_type = models.CharField(
        max_length=20, choices=ServiceType.choices, default=ServiceType.OTHER
    )
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=16, choices=OperationalStatus.choices, default=OperationalStatus.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["vendor__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["legal_entity", "vendor", "code"], name="uniq_vendor_service_code"
            )
        ]

    def __str__(self) -> str:
        return f"{self.vendor.name} / {self.name}"

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        _validate_scoped_reference(self.legal_entity_id, self.vendor, "Vendor")


class ServiceAccount(models.Model):
    """Named identity for a vendor service, not a bank or payment account."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity, on_delete=models.PROTECT, related_name="service_accounts"
    )
    service = models.ForeignKey(VendorService, on_delete=models.PROTECT, related_name="accounts")
    code = models.CharField(max_length=20, unique=True, editable=False)
    alias = models.CharField(max_length=120)
    reference = models.CharField(max_length=180, blank=True)
    status = models.CharField(
        max_length=16, choices=OperationalStatus.choices, default=OperationalStatus.ACTIVE
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["service__name", "alias"]
        constraints = [
            models.UniqueConstraint(Lower("alias"), "service", name="uniq_service_account_alias_ci")
        ]

    def __str__(self) -> str:
        return f"{self.service.name} / {self.alias}"

    def save(self, *args, **kwargs):
        self.alias = self.alias.strip()
        if not self.code:
            self.code = f"ACC-{self.id.hex[:16].upper()}"
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        _validate_scoped_reference(self.legal_entity_id, self.service, "Service")
        if self.service_id and self.alias:
            existing = ServiceAccount.objects.filter(
                service_id=self.service_id, alias__iexact=self.alias
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError({"alias": "Account alias already exists for this service."})


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
    subscription_code = models.CharField(max_length=20, unique=True, editable=False)
    service = models.ForeignKey(
        VendorService, on_delete=models.PROTECT, related_name="subscriptions", null=True, blank=True
    )
    service_account = models.ForeignKey(
        ServiceAccount,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        null=True,
        blank=True,
    )
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
    custom_cycle_days = models.PositiveIntegerField(null=True, blank=True)
    started_on = models.DateField(null=True, blank=True)
    next_renewal_date = models.DateField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True)
    reminder_days = models.JSONField(default=list)
    reminder_in_app = models.BooleanField(default=True)
    reminder_email = models.BooleanField(default=False)
    reminder_hermes = models.BooleanField(default=False)
    reminder_email_recipients = models.JSONField(default=list, blank=True)
    hermes_target = models.CharField(max_length=180, blank=True)
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
                condition=Q(service_account__isnull=True),
                name="uniq_unassigned_subscription_name",
            ),
            models.UniqueConstraint(
                fields=["legal_entity", "service_account", "name"],
                condition=Q(service_account__isnull=False),
                name="uniq_subscription_name_per_account",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.currency = self.currency.upper()
        if not self.subscription_code:
            self.subscription_code = f"SUB-{self.id.hex[:16].upper()}"
        if not self.reminder_days:
            self.reminder_days = [30, 15, 7, 3, 1, 0]
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.amount < 0:
            raise ValidationError("Subscription amount cannot be negative.")
        if self.started_on and self.next_renewal_date and self.next_renewal_date < self.started_on:
            raise ValidationError("Next renewal cannot be before the subscription start date.")
        if self.billing_cycle == BillingCycle.CUSTOM and not self.custom_cycle_days:
            raise ValidationError("Custom billing cycles require custom_cycle_days.")
        if self.custom_cycle_days is not None and self.custom_cycle_days < 1:
            raise ValidationError("custom_cycle_days must be at least 1.")
        if not isinstance(self.reminder_days, list):
            raise ValidationError("reminder_days must be a list of day offsets.")
        normalized_days = []
        for value in self.reminder_days:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 365:
                raise ValidationError("Reminder day offsets must be integers between 0 and 365.")
            if value not in normalized_days:
                normalized_days.append(value)
        self.reminder_days = sorted(normalized_days, reverse=True)
        if not isinstance(self.reminder_email_recipients, list):
            raise ValidationError("reminder_email_recipients must be a list.")
        _validate_scoped_reference(self.legal_entity_id, self.vendor, "Vendor")
        _validate_scoped_reference(self.legal_entity_id, self.service, "Service")
        _validate_scoped_reference(self.legal_entity_id, self.service_account, "Service account")
        if self.service_account_id and not self.service_id:
            raise ValidationError("A service account requires a selected service.")
        if self.service_id:
            self.service_type = self.service.service_type
            if self.vendor_id is None:
                self.vendor = self.service.vendor
            elif self.vendor_id != self.service.vendor_id:
                raise ValidationError("Subscription vendor must match its service vendor.")
        if self.service_account_id and self.service_account.service_id != self.service_id:
            raise ValidationError("Service account must belong to the selected service.")


class SubscriptionPayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="subscription_payments",
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    paid_on = models.DateField()
    previous_due_date = models.DateField(null=True, blank=True)
    next_due_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=3)
    reference = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_subscription_payments",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_on", "-created_at"]

    def __str__(self) -> str:
        return f"{self.subscription.name} payment {self.paid_on}"

    def save(self, *args, **kwargs):
        self.currency = self.currency.upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.amount < 0:
            raise ValidationError("Payment amount cannot be negative.")
        _validate_scoped_reference(self.legal_entity_id, self.subscription, "Subscription")
