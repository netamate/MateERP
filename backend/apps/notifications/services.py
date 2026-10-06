import json
from urllib import error, request

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import (
    DeliveryChannel,
    DeliveryStatus,
    Notification,
    NotificationDelivery,
)


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


def _delivery(
    *,
    subscription,
    channel: str,
    destination: str,
    days_before: int,
    due_date,
    title: str,
    message: str,
) -> NotificationDelivery:
    key = (
        f"{subscription.id}:{due_date}:{days_before}:{channel}:"
        f"{destination or 'default'}"
    )
    delivery, _ = NotificationDelivery.objects.get_or_create(
        delivery_key=key,
        defaults={
            "organization": subscription.legal_entity.organization,
            "legal_entity": subscription.legal_entity,
            "subscription": subscription,
            "channel": channel,
            "destination": destination,
            "reminder_days_before": days_before,
            "due_date": due_date,
            "title": title,
            "message": message,
        },
    )
    return delivery


def _mark_sent(delivery: NotificationDelivery) -> NotificationDelivery:
    delivery.status = DeliveryStatus.SENT
    delivery.attempt_count += 1
    delivery.last_error = ""
    delivery.sent_at = timezone.now()
    delivery.save(
        update_fields=[
            "status",
            "attempt_count",
            "last_error",
            "sent_at",
            "updated_at",
        ]
    )
    return delivery


def _mark_failed(delivery: NotificationDelivery, exc: Exception) -> NotificationDelivery:
    delivery.status = DeliveryStatus.FAILED
    delivery.attempt_count += 1
    delivery.last_error = str(exc)[:2000]
    delivery.save(
        update_fields=["status", "attempt_count", "last_error", "updated_at"]
    )
    return delivery


def deliver_in_app(
    *,
    subscription,
    recipient,
    days_before: int,
    due_date,
    severity: str,
    title: str,
    message: str,
) -> NotificationDelivery:
    delivery = _delivery(
        subscription=subscription,
        channel=DeliveryChannel.IN_APP,
        destination=recipient.email,
        days_before=days_before,
        due_date=due_date,
        title=title,
        message=message,
    )
    if delivery.status == DeliveryStatus.SENT:
        return delivery
    try:
        upsert_notification(
            organization=subscription.legal_entity.organization,
            legal_entity=subscription.legal_entity,
            recipient=recipient,
            dedupe_key=delivery.delivery_key,
            kind="RENEWAL_DUE",
            severity=severity,
            title=title,
            message=message,
            link="/operations/subscriptions",
            due_date=due_date,
        )
        return _mark_sent(delivery)
    except Exception as exc:
        return _mark_failed(delivery, exc)


def deliver_email(
    *,
    subscription,
    destination: str,
    days_before: int,
    due_date,
    title: str,
    message: str,
) -> NotificationDelivery:
    delivery = _delivery(
        subscription=subscription,
        channel=DeliveryChannel.EMAIL,
        destination=destination,
        days_before=days_before,
        due_date=due_date,
        title=title,
        message=message,
    )
    if delivery.status == DeliveryStatus.SENT:
        return delivery
    try:
        send_mail(
            subject=title,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[destination],
            fail_silently=False,
        )
        return _mark_sent(delivery)
    except Exception as exc:
        return _mark_failed(delivery, exc)


def deliver_hermes(
    *,
    subscription,
    destination: str,
    days_before: int,
    due_date,
    title: str,
    message: str,
) -> NotificationDelivery:
    delivery = _delivery(
        subscription=subscription,
        channel=DeliveryChannel.HERMES,
        destination=destination,
        days_before=days_before,
        due_date=due_date,
        title=title,
        message=message,
    )
    if delivery.status == DeliveryStatus.SENT:
        return delivery

    webhook_url = settings.MATEERP_HERMES_WEBHOOK_URL
    if not webhook_url:
        return _mark_failed(
            delivery,
            RuntimeError("MATEERP_HERMES_WEBHOOK_URL is not configured."),
        )

    payload = json.dumps(
        {
            "event": "mateerp.subscription_reminder",
            "target": destination,
            "title": title,
            "message": message,
            "subscription": {
                "id": str(subscription.id),
                "name": subscription.name,
                "type": subscription.service_type,
                "vendor": subscription.vendor.name if subscription.vendor else None,
                "amount": str(subscription.amount),
                "currency": subscription.currency,
                "due_date": str(due_date),
                "days_before": days_before,
                "payment_method": subscription.payment_method,
                "reference": subscription.reference,
            },
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if settings.MATEERP_HERMES_WEBHOOK_TOKEN:
        headers["Authorization"] = (
            f"Bearer {settings.MATEERP_HERMES_WEBHOOK_TOKEN}"
        )

    try:
        webhook_request = request.Request(
            webhook_url,
            data=payload,
            headers=headers,
            method="POST",
        )
        with request.urlopen(webhook_request, timeout=15) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"Hermes returned HTTP {response.status}.")
        return _mark_sent(delivery)
    except (error.URLError, TimeoutError, RuntimeError) as exc:
        return _mark_failed(delivery, exc)
