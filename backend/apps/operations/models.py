import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Sum
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


class BillingMode(models.TextChoices):
    FIXED = "FIXED", "Fixed"
    PAYG = "PAYG", "Pay as you go"


def default_budget_alert_thresholds():
    return [50, 80, 100]


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
    billing_mode = models.CharField(
        max_length=12,
        choices=BillingMode.choices,
        default=BillingMode.FIXED,
    )
    estimated_cost = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal("0"),
    )
    monthly_budget = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
    )
    budget_alert_thresholds = models.JSONField(default=default_budget_alert_thresholds)
    usage_unit = models.CharField(max_length=40, blank=True)
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
    email_notifications_enabled = models.BooleanField(default=False)
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
        if self.estimated_cost < 0:
            raise ValidationError("Estimated cost cannot be negative.")
        if self.monthly_budget is not None and self.monthly_budget <= 0:
            raise ValidationError("Monthly budget must be greater than zero.")
        if not isinstance(self.budget_alert_thresholds, list):
            raise ValidationError("Budget alert thresholds must be a list.")
        normalized_thresholds = []
        for value in self.budget_alert_thresholds:
            if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > 500:
                raise ValidationError(
                    "Budget alert thresholds must be integer percentages between 1 and 500."
                )
            if value not in normalized_thresholds:
                normalized_thresholds.append(value)
        self.budget_alert_thresholds = sorted(normalized_thresholds)
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


class BillingPeriodStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    AWAITING_INVOICE = "AWAITING_INVOICE", "Awaiting invoice"
    INVOICED = "INVOICED", "Invoiced"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Partially paid"
    PAID = "PAID", "Paid"
    CLOSED = "CLOSED", "Closed"


class BillingInvoiceStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Partially paid"
    PAID = "PAID", "Paid"
    VOID = "VOID", "Void"


class SubscriptionBillingPeriod(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="subscription_billing_periods",
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.PROTECT,
        related_name="billing_periods",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    estimated_cost = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal("0"),
    )
    current_usage_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal("0"),
    )
    usage_quantity = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        null=True,
        blank=True,
    )
    usage_unit = models.CharField(max_length=40, blank=True)
    current_usage_updated_at = models.DateTimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_subscription_billing_periods",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_end", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["subscription", "period_start", "period_end"],
                name="uniq_subscription_billing_period",
            )
        ]
        indexes = [
            models.Index(
                fields=["legal_entity", "period_end"],
                name="billing_period_entity_end_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.subscription.name} {self.period_start} - {self.period_end}"

    def save(self, *args, **kwargs):
        if not self.usage_unit and self.subscription_id:
            self.usage_unit = self.subscription.usage_unit
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.period_end < self.period_start:
            raise ValidationError("Billing period end cannot be before the start date.")
        if self.estimated_cost < 0 or self.current_usage_amount < 0:
            raise ValidationError("Billing estimates and usage costs cannot be negative.")
        if self.usage_quantity is not None and self.usage_quantity < 0:
            raise ValidationError("Usage quantity cannot be negative.")
        _validate_scoped_reference(
            self.legal_entity_id,
            self.subscription,
            "Subscription",
        )


class SubscriptionInvoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="subscription_invoices",
    )
    billing_period = models.ForeignKey(
        SubscriptionBillingPeriod,
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="subscription_invoices",
    )
    invoice_number = models.CharField(max_length=180)
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3)
    subtotal = models.DecimalField(max_digits=20, decimal_places=2)
    tax_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal("0"),
    )
    total_amount = models.DecimalField(max_digits=20, decimal_places=2)
    document = models.OneToOneField(
        "finance.FinanceDocument",
        on_delete=models.PROTECT,
        related_name="subscription_invoice",
        null=True,
        blank=True,
    )
    expense = models.OneToOneField(
        "finance.Expense",
        on_delete=models.PROTECT,
        related_name="subscription_invoice",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=BillingInvoiceStatus.choices,
        default=BillingInvoiceStatus.OPEN,
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_subscription_invoices",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-invoice_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                Lower("invoice_number"),
                "vendor",
                name="uniq_billing_invoice_vendor_number_ci",
            )
        ]
        indexes = [
            models.Index(
                fields=["legal_entity", "status", "invoice_date"],
                name="billing_invoice_status_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.vendor.name} {self.invoice_number}"

    def save(self, *args, **kwargs):
        self.invoice_number = self.invoice_number.strip()
        self.currency = self.currency.upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if not self.invoice_number:
            raise ValidationError("Invoice number is required.")
        if self.subtotal < 0 or self.tax_amount < 0 or self.total_amount <= 0:
            raise ValidationError("Invoice amounts must be valid positive values.")
        if self.subtotal + self.tax_amount != self.total_amount:
            raise ValidationError("Invoice total must equal subtotal plus tax.")
        if self.due_date and self.due_date < self.invoice_date:
            raise ValidationError("Invoice due date cannot be before invoice date.")
        for record, label in (
            (self.billing_period, "Billing period"),
            (self.vendor, "Vendor"),
            (self.document, "Document"),
            (self.expense, "Expense"),
        ):
            _validate_scoped_reference(self.legal_entity_id, record, label)
        if self.billing_period_id:
            subscription = self.billing_period.subscription
            if subscription.vendor_id and subscription.vendor_id != self.vendor_id:
                raise ValidationError("Invoice vendor must match the subscription vendor.")
            if self.currency != subscription.currency:
                raise ValidationError("Invoice currency must match the subscription currency.")
        if self.document_id and self.document.document_type != "INVOICE":
            raise ValidationError("Linked finance document must be an invoice.")
        if self.expense_id:
            if self.expense.vendor_id and self.expense.vendor_id != self.vendor_id:
                raise ValidationError("Expense vendor must match the invoice vendor.")
            if self.expense.currency != self.currency:
                raise ValidationError("Expense currency must match the invoice currency.")


class BillingPayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        LegalEntity,
        on_delete=models.PROTECT,
        related_name="billing_payments",
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.PROTECT,
        related_name="billing_payments",
    )
    payment_code = models.CharField(max_length=20, unique=True, editable=False)
    paid_on = models.DateField()
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=3)
    reference = models.CharField(max_length=180, blank=True)
    financial_account = models.ForeignKey(
        "finance.FinancialAccount",
        on_delete=models.PROTECT,
        related_name="billing_payments",
        null=True,
        blank=True,
    )
    expense_payment = models.OneToOneField(
        "finance.ExpensePayment",
        on_delete=models.PROTECT,
        related_name="billing_payment",
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_billing_payments",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_on", "-created_at"]
        indexes = [
            models.Index(
                fields=["legal_entity", "paid_on"],
                name="billing_payment_entity_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.payment_code} {self.amount} {self.currency}"

    def save(self, *args, **kwargs):
        if not self.payment_code:
            self.payment_code = f"PAY-{self.id.hex[:16].upper()}"
        self.currency = self.currency.upper()
        if self.expense_payment_id and not self.financial_account_id:
            self.financial_account = self.expense_payment.financial_account
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.amount <= 0:
            raise ValidationError("Payment amount must be greater than zero.")
        _validate_scoped_reference(
            self.legal_entity_id,
            self.subscription,
            "Subscription",
        )
        _validate_scoped_reference(
            self.legal_entity_id,
            self.financial_account,
            "Financial account",
        )
        _validate_scoped_reference(
            self.legal_entity_id,
            self.expense_payment,
            "Expense payment",
        )
        if self.currency != self.subscription.currency:
            raise ValidationError("Payment currency must match the subscription currency.")
        if self.financial_account_id and self.financial_account.currency != self.currency:
            raise ValidationError("Financial account currency must match the payment currency.")
        if self.expense_payment_id:
            if self.expense_payment.amount != self.amount:
                raise ValidationError("Linked expense payment amount must match this payment.")
            if self.expense_payment.currency != self.currency:
                raise ValidationError("Linked expense payment currency must match this payment.")
            if (
                self.financial_account_id
                and self.expense_payment.financial_account_id != self.financial_account_id
            ):
                raise ValidationError("Linked expense payment must use the same financial account.")


class BillingPaymentAllocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(
        BillingPayment,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    invoice = models.ForeignKey(
        SubscriptionInvoice,
        on_delete=models.PROTECT,
        related_name="payment_allocations",
    )
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["payment", "invoice"],
                name="uniq_billing_payment_invoice_allocation",
            )
        ]

    def __str__(self) -> str:
        return f"{self.payment.payment_code} -> {self.invoice.invoice_number}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.amount <= 0:
            raise ValidationError("Allocation amount must be greater than zero.")
        if not self.payment_id or not self.invoice_id:
            return
        period_subscription_id = self.invoice.billing_period.subscription_id
        if self.payment.subscription_id != period_subscription_id:
            raise ValidationError("Payment and invoice must belong to the same subscription.")
        if self.payment.currency != self.invoice.currency:
            raise ValidationError("Payment and invoice currencies must match.")

        other_payment_allocations = BillingPaymentAllocation.objects.filter(
            payment=self.payment
        ).exclude(pk=self.pk)
        payment_allocated = other_payment_allocations.aggregate(total=Sum("amount"))[
            "total"
        ] or Decimal("0")
        if payment_allocated + self.amount > self.payment.amount:
            raise ValidationError("Allocation exceeds the unallocated payment amount.")

        other_invoice_allocations = BillingPaymentAllocation.objects.filter(
            invoice=self.invoice
        ).exclude(pk=self.pk)
        invoice_paid = other_invoice_allocations.aggregate(total=Sum("amount"))["total"] or Decimal(
            "0"
        )
        if invoice_paid + self.amount > self.invoice.total_amount:
            raise ValidationError("Allocation exceeds the outstanding invoice balance.")
