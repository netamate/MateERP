from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import F
from django.utils import timezone

from apps.identity.models import LegalEntity, Membership, MembershipStatus
from apps.identity.policy import Permission, has_permission
from apps.operations.models import OperationalStatus, Subscription

from ...models import (
    DeliveryChannel,
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationKind,
    NotificationSeverity,
)
from ...services import (
    deliver_email,
    deliver_hermes,
    deliver_in_app,
    resolve_notifications,
)


class Command(BaseCommand):
    help = "Deliver idempotent MateERP subscription reminders."

    def add_arguments(self, parser):
        parser.add_argument(
            "--horizon-days",
            type=int,
            default=365,
            help="Ignore subscriptions due beyond this many days.",
        )

    def handle(self, *args, **options):
        horizon_days = options["horizon_days"]
        if horizon_days < 0 or horizon_days > 365:
            raise ValueError("--horizon-days must be between 0 and 365.")

        today = timezone.localdate()
        end_date = today + timedelta(days=horizon_days)
        sent = 0
        failed = 0

        for entity in LegalEntity.objects.filter(status="ACTIVE").select_related(
            "organization"
        ):
            viewers = self._viewers(entity)
            subscriptions = (
                Subscription.objects.filter(
                    legal_entity=entity,
                    status=OperationalStatus.ACTIVE,
                    next_renewal_date__isnull=False,
                    next_renewal_date__gte=today,
                    next_renewal_date__lte=end_date,
                )
                .select_related("vendor", "legal_entity__organization")
                .order_by("next_renewal_date", "name")
            )

            for subscription in subscriptions:
                days_remaining = (subscription.next_renewal_date - today).days
                if days_remaining not in subscription.reminder_days:
                    continue

                severity = self._severity(days_remaining)
                title, message = self._content(subscription, days_remaining)

                if subscription.reminder_in_app:
                    for membership in viewers:
                        delivery = deliver_in_app(
                            subscription=subscription,
                            recipient=membership.user,
                            days_before=days_remaining,
                            due_date=subscription.next_renewal_date,
                            severity=severity,
                            title=title,
                            message=message,
                        )
                        sent, failed = self._count(delivery, sent, failed)

                if subscription.reminder_email:
                    recipients = subscription.reminder_email_recipients or [
                        membership.user.email for membership in viewers
                    ]
                    for destination in dict.fromkeys(recipients):
                        delivery = deliver_email(
                            subscription=subscription,
                            destination=destination,
                            days_before=days_remaining,
                            due_date=subscription.next_renewal_date,
                            title=title,
                            message=message,
                        )
                        sent, failed = self._count(delivery, sent, failed)

                if subscription.reminder_hermes:
                    delivery = deliver_hermes(
                        subscription=subscription,
                        destination=subscription.hermes_target or "default",
                        days_before=days_remaining,
                        due_date=subscription.next_renewal_date,
                        title=title,
                        message=message,
                    )
                    sent, failed = self._count(delivery, sent, failed)

            self._resolve_stale_in_app(entity, viewers)

        self.stdout.write(
            self.style.SUCCESS(
                f"Reminder refresh complete: {sent} sent, {failed} failed."
            )
        )

    @staticmethod
    def _count(delivery, sent, failed):
        if delivery.status == DeliveryStatus.SENT:
            sent += 1
        elif delivery.status == DeliveryStatus.FAILED:
            failed += 1
        return sent, failed

    @staticmethod
    def _severity(days_remaining):
        if days_remaining <= 3:
            return NotificationSeverity.CRITICAL
        if days_remaining <= 7:
            return NotificationSeverity.WARNING
        return NotificationSeverity.INFO

    @staticmethod
    def _content(subscription, days_remaining):
        if days_remaining == 0:
            timing = "due today"
        elif days_remaining == 1:
            timing = "due tomorrow"
        else:
            timing = f"due in {days_remaining} days"

        title = f"Payment reminder: {subscription.name} — {timing}"
        message = (
            f"{subscription.name} is {timing} on "
            f"{subscription.next_renewal_date}. "
            f"Amount: {subscription.amount} {subscription.currency}."
        )
        if subscription.vendor:
            message += f" Vendor: {subscription.vendor.name}."
        if subscription.payment_method:
            message += f" Payment method: {subscription.payment_method}."
        return title, message

    @staticmethod
    def _viewers(entity):
        memberships = Membership.objects.filter(
            organization=entity.organization,
            status=MembershipStatus.ACTIVE,
        ).select_related("user")
        return [
            membership
            for membership in memberships
            if has_permission(membership, Permission.VIEW_NOTIFICATIONS)
            and (
                membership.all_legal_entities
                or membership.legal_entities.filter(id=entity.id).exists()
            )
        ]

    @staticmethod
    def _resolve_stale_in_app(entity, viewers):
        valid_deliveries = NotificationDelivery.objects.filter(
            legal_entity=entity,
            channel=DeliveryChannel.IN_APP,
            status=DeliveryStatus.SENT,
            subscription__status=OperationalStatus.ACTIVE,
            due_date=F("subscription__next_renewal_date"),
        )

        for membership in viewers:
            valid_keys = list(
                valid_deliveries.filter(destination=membership.user.email).values_list(
                    "delivery_key",
                    flat=True,
                )
            )
            stale = Notification.objects.filter(
                organization=entity.organization,
                legal_entity=entity,
                recipient=membership.user,
                kind=NotificationKind.RENEWAL_DUE,
                resolved_at__isnull=True,
            )
            if valid_keys:
                stale = stale.exclude(dedupe_key__in=valid_keys)
            resolve_notifications(stale)
