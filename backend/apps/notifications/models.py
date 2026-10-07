import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class NotificationKind(models.TextChoices):
    RENEWAL_DUE = "RENEWAL_DUE", "Renewal due"
    BUDGET_THRESHOLD = "BUDGET_THRESHOLD", "Budget threshold"
    MISSING_INVOICE = "MISSING_INVOICE", "Missing invoice"
    INVOICE_OVERDUE = "INVOICE_OVERDUE", "Invoice overdue"
    RECONCILIATION_NEEDED = "RECONCILIATION_NEEDED", "Reconciliation needed"
    SYSTEM = "SYSTEM", "System"


class AlertFrequency(models.TextChoices):
    HOURLY = "HOURLY", "Hourly"
    DAILY = "DAILY", "Daily"


def default_renewal_days():
    return [30, 15, 7, 3, 1, 0]


class NotificationSeverity(models.TextChoices):
    INFO = "INFO", "Info"
    WARNING = "WARNING", "Warning"
    CRITICAL = "CRITICAL", "Critical"


class DeliveryChannel(models.TextChoices):
    IN_APP = "IN_APP", "In-app"
    EMAIL = "EMAIL", "Email"
    HERMES = "HERMES", "Hermes"


class DeliveryStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"


class DirectEmailStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SCHEDULED = "SCHEDULED", "Scheduled"
    SENDING = "SENDING", "Sending"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "identity.Organization",
        on_delete=models.PROTECT,
        related_name="notifications",
    )
    legal_entity = models.ForeignKey(
        "identity.LegalEntity",
        on_delete=models.PROTECT,
        related_name="notifications",
        null=True,
        blank=True,
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=32, choices=NotificationKind.choices)
    severity = models.CharField(
        max_length=16,
        choices=NotificationSeverity.choices,
        default=NotificationSeverity.INFO,
    )
    dedupe_key = models.CharField(max_length=180)
    title = models.CharField(max_length=180)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True)
    due_date = models.DateField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["resolved_at", "read_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "recipient", "dedupe_key"],
                name="uniq_notification_recipient_key",
            )
        ]
        indexes = [
            models.Index(
                fields=["recipient", "resolved_at", "read_at", "created_at"],
                name="notification_inbox_idx",
            ),
            models.Index(
                fields=["legal_entity", "due_date"],
                name="notification_due_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.recipient}: {self.title}"


class AlertRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "identity.Organization",
        on_delete=models.CASCADE,
        related_name="alert_rules",
    )
    legal_entity = models.ForeignKey(
        "identity.LegalEntity",
        on_delete=models.CASCADE,
        related_name="alert_rules",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=180)
    signal = models.CharField(max_length=32, choices=NotificationKind.choices)
    enabled = models.BooleanField(default=True)
    severity = models.CharField(
        max_length=16,
        choices=NotificationSeverity.choices,
        default=NotificationSeverity.WARNING,
    )
    frequency = models.CharField(
        max_length=16,
        choices=AlertFrequency.choices,
        default=AlertFrequency.DAILY,
    )
    schedule_hour = models.PositiveSmallIntegerField(default=8)
    schedule_timezone = models.CharField(max_length=64, default="UTC")
    in_app_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=False)
    hermes_enabled = models.BooleanField(default=False)
    recipient_user_ids = models.JSONField(default=list, blank=True)
    email_recipients = models.JSONField(default=list, blank=True)
    hermes_target = models.CharField(max_length=180, blank=True)
    renewal_days = models.JSONField(default=default_renewal_days)
    grace_days = models.PositiveSmallIntegerField(default=1)
    respect_subscription_channels = models.BooleanField(default=False)
    last_evaluated_at = models.DateTimeField(null=True, blank=True)
    last_delivery_count = models.PositiveIntegerField(default=0)
    last_failure_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_alert_rules",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="updated_alert_rules",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["signal", "legal_entity_id", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "legal_entity", "signal"],
                name="uniq_alert_rule_scope_signal",
                nulls_distinct=False,
            )
        ]
        indexes = [
            models.Index(
                fields=["organization", "enabled", "signal"],
                name="alert_rule_org_signal_idx",
            ),
            models.Index(
                fields=["legal_entity", "enabled", "signal"],
                name="alert_rule_entity_signal_idx",
            ),
        ]

    def __str__(self) -> str:
        scope = self.legal_entity.name if self.legal_entity_id else self.organization.name
        return f"{scope} · {self.name}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.legal_entity_id and self.legal_entity.organization_id != self.organization_id:
            raise ValidationError("Alert rule legal entity must belong to the organization.")
        if self.schedule_hour > 23:
            raise ValidationError("Schedule hour must be between 0 and 23.")
        try:
            ZoneInfo(self.schedule_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValidationError("Schedule timezone is not a valid IANA timezone.") from exc
        if not isinstance(self.recipient_user_ids, list):
            raise ValidationError("Recipient user IDs must be a list.")
        if not isinstance(self.email_recipients, list):
            raise ValidationError("Email recipients must be a list.")
        if not isinstance(self.renewal_days, list):
            raise ValidationError("Renewal days must be a list.")
        normalized_days = []
        for value in self.renewal_days:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 365:
                raise ValidationError("Renewal days must contain integers between 0 and 365.")
            if value not in normalized_days:
                normalized_days.append(value)
        self.renewal_days = sorted(normalized_days, reverse=True)


class NotificationDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "identity.Organization",
        on_delete=models.PROTECT,
        related_name="notification_deliveries",
    )
    legal_entity = models.ForeignKey(
        "identity.LegalEntity",
        on_delete=models.PROTECT,
        related_name="notification_deliveries",
    )
    subscription = models.ForeignKey(
        "operations.Subscription",
        on_delete=models.PROTECT,
        related_name="notification_deliveries",
        null=True,
        blank=True,
    )
    alert_rule = models.ForeignKey(
        AlertRule,
        on_delete=models.SET_NULL,
        related_name="deliveries",
        null=True,
        blank=True,
    )
    delivery_key = models.CharField(max_length=255, unique=True)
    signal = models.CharField(
        max_length=32,
        choices=NotificationKind.choices,
        default=NotificationKind.RENEWAL_DUE,
    )
    source_type = models.CharField(max_length=64, blank=True)
    source_id = models.CharField(max_length=64, blank=True)
    channel = models.CharField(max_length=16, choices=DeliveryChannel.choices)
    destination = models.CharField(max_length=255, blank=True)
    reminder_days_before = models.PositiveSmallIntegerField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    severity = models.CharField(
        max_length=16,
        choices=NotificationSeverity.choices,
        default=NotificationSeverity.INFO,
    )
    title = models.CharField(max_length=180)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True)
    context = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
    )
    attempt_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["subscription", "due_date", "channel"],
                name="delivery_subscription_idx",
            ),
            models.Index(
                fields=["status", "created_at"],
                name="delivery_status_idx",
            ),
            models.Index(
                fields=["alert_rule", "signal", "status"],
                name="delivery_rule_signal_idx",
            ),
            models.Index(
                fields=["legal_entity", "signal", "created_at"],
                name="delivery_entity_signal_idx",
            ),
        ]

    def __str__(self) -> str:
        source = self.subscription.name if self.subscription_id else self.source_type or self.signal
        return f"{source} · {self.channel} · {self.status}"


class NotificationIntegrationSettings(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField(
        "identity.Organization",
        on_delete=models.CASCADE,
        related_name="notification_integration_settings",
    )
    smtp_enabled = models.BooleanField(default=False)
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_username = models.CharField(max_length=255, blank=True)
    smtp_password_encrypted = models.TextField(blank=True)
    smtp_use_tls = models.BooleanField(default=True)
    smtp_use_ssl = models.BooleanField(default=False)
    smtp_from_name = models.CharField(max_length=180, default="MateERP", blank=True)
    smtp_from_email = models.EmailField(blank=True)

    hermes_enabled = models.BooleanField(default=False)
    hermes_webhook_url = models.URLField(blank=True)
    hermes_token_encrypted = models.TextField(blank=True)
    hermes_default_target = models.CharField(max_length=180, blank=True)

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="updated_notification_integrations",
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "notification integration settings"
        verbose_name_plural = "notification integration settings"

    def __str__(self) -> str:
        return f"{self.organization.name} integrations"


class DirectEmailNotification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "identity.Organization",
        on_delete=models.PROTECT,
        related_name="direct_email_notifications",
    )
    legal_entity = models.ForeignKey(
        "identity.LegalEntity",
        on_delete=models.PROTECT,
        related_name="direct_email_notifications",
        null=True,
        blank=True,
    )
    to_recipients = models.JSONField(default=list)
    cc_recipients = models.JSONField(default=list, blank=True)
    bcc_recipients = models.JSONField(default=list, blank=True)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    scheduled_for = models.DateTimeField(null=True, blank=True)
    schedule_timezone = models.CharField(max_length=64, default="UTC")
    status = models.CharField(
        max_length=16,
        choices=DirectEmailStatus.choices,
        default=DirectEmailStatus.DRAFT,
    )
    attempt_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_direct_email_notifications",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["organization", "status", "scheduled_for"],
                name="direct_email_due_idx",
            ),
            models.Index(
                fields=["legal_entity", "created_at"],
                name="direct_email_entity_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.subject} · {self.status}"
