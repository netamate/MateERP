from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import DirectEmailNotification, DirectEmailStatus
from .services import _send_email

STALE_SENDING_AFTER = timedelta(minutes=15)


def deliver_direct_email(notification_id) -> DirectEmailNotification:
    with transaction.atomic():
        notification = DirectEmailNotification.objects.select_for_update().get(id=notification_id)
        if notification.status in {
            DirectEmailStatus.SENT,
            DirectEmailStatus.CANCELLED,
            DirectEmailStatus.SENDING,
        }:
            return notification
        notification.status = DirectEmailStatus.SENDING
        notification.attempt_count += 1
        notification.last_error = ""
        notification.save(update_fields=["status", "attempt_count", "last_error", "updated_at"])

    try:
        _send_email(
            organization=notification.organization,
            destinations=notification.to_recipients,
            cc=notification.cc_recipients,
            bcc=notification.bcc_recipients,
            subject=notification.subject,
            message=notification.body,
        )
    except Exception as exc:
        DirectEmailNotification.objects.filter(id=notification.id).update(
            status=DirectEmailStatus.FAILED,
            last_error=str(exc)[:2000],
            updated_at=timezone.now(),
        )
    else:
        DirectEmailNotification.objects.filter(id=notification.id).update(
            status=DirectEmailStatus.SENT,
            last_error="",
            sent_at=timezone.now(),
            updated_at=timezone.now(),
        )

    return DirectEmailNotification.objects.get(id=notification.id)


def recover_stale_direct_emails() -> int:
    cutoff = timezone.now() - STALE_SENDING_AFTER
    return DirectEmailNotification.objects.filter(
        status=DirectEmailStatus.SENDING,
        updated_at__lt=cutoff,
    ).update(
        status=DirectEmailStatus.FAILED,
        last_error=(
            "The previous send attempt did not complete. Review the message and retry it manually."
        ),
        updated_at=timezone.now(),
    )
