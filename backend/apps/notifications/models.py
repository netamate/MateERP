import uuid

from django.conf import settings
from django.db import models


class NotificationKind(models.TextChoices):
    RENEWAL_DUE = "RENEWAL_DUE", "Renewal due"
    EXPENSE_APPROVAL = "EXPENSE_APPROVAL", "Expense approval"
    REIMBURSEMENT_APPROVAL = "REIMBURSEMENT_APPROVAL", "Reimbursement approval"
    SYSTEM = "SYSTEM", "System"


class NotificationSeverity(models.TextChoices):
    INFO = "INFO", "Info"
    WARNING = "WARNING", "Warning"
    CRITICAL = "CRITICAL", "Critical"


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["read_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "recipient", "dedupe_key"],
                name="uniq_notification_recipient_key",
            )
        ]
        indexes = [
            models.Index(
                fields=["recipient", "read_at", "created_at"],
                name="notification_inbox_idx",
            ),
            models.Index(
                fields=["legal_entity", "due_date"],
                name="notification_due_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.recipient}: {self.title}"
