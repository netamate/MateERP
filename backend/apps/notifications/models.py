import uuid

from django.conf import settings
from django.db import models


class NotificationKind(models.TextChoices):
    RENEWAL_DUE = "RENEWAL_DUE", "Renewal due"
    SYSTEM = "SYSTEM", "System"


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
    )
    delivery_key = models.CharField(max_length=255, unique=True)
    channel = models.CharField(max_length=16, choices=DeliveryChannel.choices)
    destination = models.CharField(max_length=255, blank=True)
    reminder_days_before = models.PositiveSmallIntegerField()
    due_date = models.DateField()
    title = models.CharField(max_length=180)
    message = models.TextField()
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
        ]

    def __str__(self) -> str:
        return f"{self.subscription.name} · {self.channel} · {self.status}"


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
