from apps.notifications.direct_email import (
    deliver_direct_email,
    recover_stale_direct_emails,
)
from apps.notifications.models import DirectEmailNotification, DirectEmailStatus
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Send due MateERP direct email notifications."

    def handle(self, *args, **options):
        recovered = recover_stale_direct_emails()
        due_ids = list(
            DirectEmailNotification.objects.filter(
                status=DirectEmailStatus.SCHEDULED,
                scheduled_for__lte=timezone.now(),
            )
            .order_by("scheduled_for")
            .values_list("id", flat=True)[:200]
        )

        sent = 0
        failed = 0
        for notification_id in due_ids:
            notification = deliver_direct_email(notification_id)
            if notification.status == DirectEmailStatus.SENT:
                sent += 1
            elif notification.status == DirectEmailStatus.FAILED:
                failed += 1

        self.stdout.write(
            f"Direct email scheduler complete: {sent} sent, "
            f"{failed} failed, {recovered} stale attempts recovered."
        )
