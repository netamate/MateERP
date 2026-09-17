from django.utils import timezone

from .models import Notification


def upsert_notification(
    *,
    organization,
    legal_entity,
    recipient,
    dedupe_key: str,
    kind: str,
    severity: str,
    title: str,
    message: str,
    link: str = "",
    due_date=None,
) -> Notification:
    notification, _ = Notification.objects.update_or_create(
        organization=organization,
        recipient=recipient,
        dedupe_key=dedupe_key,
        defaults={
            "legal_entity": legal_entity,
            "kind": kind,
            "severity": severity,
            "title": title,
            "message": message,
            "link": link,
            "due_date": due_date,
            "resolved_at": None,
        },
    )
    return notification


def resolve_notifications(queryset) -> int:
    return queryset.filter(resolved_at__isnull=True).update(resolved_at=timezone.now())


def mark_notification_read(notification: Notification) -> Notification:
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at", "updated_at"])
    return notification


def mark_all_notifications_read(queryset) -> int:
    return queryset.filter(read_at__isnull=True).update(read_at=timezone.now())
