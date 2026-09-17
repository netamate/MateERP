import uuid

from django.conf import settings
from django.db import models


class AuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise TypeError("Audit events are append-only.")

    def delete(self):
        raise TypeError("Audit events are append-only.")


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "identity.Organization",
        on_delete=models.PROTECT,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    legal_entity = models.ForeignKey(
        "identity.LegalEntity",
        on_delete=models.PROTECT,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=120)
    object_type = models.CharField(max_length=120)
    object_id = models.CharField(max_length=64)
    previous_state = models.JSONField(default=dict, blank=True)
    new_state = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AuditEventQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["organization", "created_at"], name="audit_org_created_idx"
            ),
            models.Index(fields=["object_type", "object_id"], name="audit_object_idx"),
            models.Index(fields=["action", "created_at"], name="audit_action_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.object_type}:{self.object_id}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise TypeError("Audit events are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError("Audit events are append-only.")
