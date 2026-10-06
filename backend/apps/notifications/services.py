import json
from email.utils import parseaddr
from urllib import error, request

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.utils import timezone

from .crypto import decrypt_secret
from .models import (
    DeliveryChannel,
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationIntegrationSettings,
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


def integration_settings_for(organization):
    return NotificationIntegrationSettings.objects.filter(organization=organization).first()


def integration_settings_payload(organization) -> dict:
    configured = integration_settings_for(organization)
    if configured:
        return {
            "smtp_enabled": configured.smtp_enabled,
            "smtp_host": configured.smtp_host,
            "smtp_port": configured.smtp_port,
            "smtp_username": configured.smtp_username,
            "smtp_password_configured": bool(configured.smtp_password_encrypted),
            "smtp_use_tls": configured.smtp_use_tls,
            "smtp_use_ssl": configured.smtp_use_ssl,
            "smtp_from_name": configured.smtp_from_name,
            "smtp_from_email": configured.smtp_from_email,
            "smtp_source": "ERP",
            "hermes_enabled": configured.hermes_enabled,
            "hermes_webhook_url": configured.hermes_webhook_url,
            "hermes_token_configured": bool(configured.hermes_token_encrypted),
            "hermes_default_target": configured.hermes_default_target,
            "hermes_source": "ERP",
            "updated_at": configured.updated_at.isoformat() if configured.updated_at else None,
        }

    return {
        "smtp_enabled": bool(settings.EMAIL_HOST),
        "smtp_host": settings.EMAIL_HOST,
        "smtp_port": settings.EMAIL_PORT,
        "smtp_username": settings.EMAIL_HOST_USER,
        "smtp_password_configured": bool(settings.EMAIL_HOST_PASSWORD),
        "smtp_use_tls": settings.EMAIL_USE_TLS,
        "smtp_use_ssl": settings.EMAIL_USE_SSL,
        "smtp_from_name": parseaddr(settings.DEFAULT_FROM_EMAIL)[0] or "MateERP",
        "smtp_from_email": parseaddr(settings.DEFAULT_FROM_EMAIL)[1],
        "smtp_source": "ENV" if settings.EMAIL_HOST else "NONE",
        "hermes_enabled": bool(settings.MATEERP_HERMES_WEBHOOK_URL),
        "hermes_webhook_url": settings.MATEERP_HERMES_WEBHOOK_URL,
        "hermes_token_configured": bool(settings.MATEERP_HERMES_WEBHOOK_TOKEN),
        "hermes_default_target": "",
        "hermes_source": "ENV" if settings.MATEERP_HERMES_WEBHOOK_URL else "NONE",
        "updated_at": None,
    }


def _email_config(organization) -> dict:
    configured = integration_settings_for(organization)
    if configured:
        if not configured.smtp_enabled:
            raise RuntimeError("SMTP delivery is disabled in ERP Settings.")
        if not configured.smtp_host:
            raise RuntimeError("SMTP host is not configured in ERP Settings.")
        if not configured.smtp_from_email:
            raise RuntimeError("SMTP From Email is not configured in ERP Settings.")
        return {
            "backend": "django.core.mail.backends.smtp.EmailBackend",
            "host": configured.smtp_host,
            "port": configured.smtp_port,
            "username": configured.smtp_username,
            "password": decrypt_secret(configured.smtp_password_encrypted),
            "use_tls": configured.smtp_use_tls,
            "use_ssl": configured.smtp_use_ssl,
            "from_email": (
                f"{configured.smtp_from_name} <{configured.smtp_from_email}>"
                if configured.smtp_from_name
                else configured.smtp_from_email
            ),
        }

    return {
        "backend": settings.EMAIL_BACKEND,
        "host": settings.EMAIL_HOST,
        "port": settings.EMAIL_PORT,
        "username": settings.EMAIL_HOST_USER,
        "password": settings.EMAIL_HOST_PASSWORD,
        "use_tls": settings.EMAIL_USE_TLS,
        "use_ssl": settings.EMAIL_USE_SSL,
        "from_email": settings.DEFAULT_FROM_EMAIL,
    }


def _send_email(*, organization, destination: str, subject: str, message: str) -> None:
    config = _email_config(organization)
    connection = get_connection(
        backend=config["backend"],
        fail_silently=False,
        host=config["host"],
        port=config["port"],
        username=config["username"],
        password=config["password"],
        use_tls=config["use_tls"],
        use_ssl=config["use_ssl"],
    )
    EmailMessage(
        subject=subject,
        body=message,
        from_email=config["from_email"],
        to=[destination],
        connection=connection,
    ).send(fail_silently=False)


def send_test_email(*, organization, destination: str) -> None:
    _send_email(
        organization=organization,
        destination=destination,
        subject="MateERP SMTP test",
        message=(
            "This is a test email from MateERP. "
            "If you received it, the SMTP integration is working."
        ),
    )


def _hermes_config(organization) -> dict:
    configured = integration_settings_for(organization)
    if configured:
        if not configured.hermes_enabled:
            raise RuntimeError("Hermes delivery is disabled in ERP Settings.")
        if not configured.hermes_webhook_url:
            raise RuntimeError("Hermes webhook URL is not configured in ERP Settings.")
        return {
            "webhook_url": configured.hermes_webhook_url,
            "token": decrypt_secret(configured.hermes_token_encrypted),
            "default_target": configured.hermes_default_target,
        }

    if not settings.MATEERP_HERMES_WEBHOOK_URL:
        raise RuntimeError("MATEERP_HERMES_WEBHOOK_URL is not configured.")
    return {
        "webhook_url": settings.MATEERP_HERMES_WEBHOOK_URL,
        "token": settings.MATEERP_HERMES_WEBHOOK_TOKEN,
        "default_target": "",
    }


def _post_hermes(*, organization, payload: dict) -> None:
    config = _hermes_config(organization)
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if config["token"]:
        headers["Authorization"] = f"Bearer {config['token']}"

    webhook_request = request.Request(
        config["webhook_url"],
        data=body,
        headers=headers,
        method="POST",
    )
    with request.urlopen(webhook_request, timeout=15) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"Hermes returned HTTP {response.status}.")


def send_test_hermes(*, organization, target: str = "") -> None:
    config = _hermes_config(organization)
    destination = target or config["default_target"] or "default"
    _post_hermes(
        organization=organization,
        payload={
            "event": "mateerp.integration_test",
            "target": destination,
            "title": "MateERP Hermes test",
            "message": "MateERP Hermes integration is working.",
        },
    )


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
    key = f"{subscription.id}:{due_date}:{days_before}:{channel}:{destination or 'default'}"
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
    delivery.save(update_fields=["status", "attempt_count", "last_error", "updated_at"])
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
        _send_email(
            organization=subscription.legal_entity.organization,
            destination=destination,
            subject=title,
            message=message,
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

    try:
        config = _hermes_config(subscription.legal_entity.organization)
        target = destination or config["default_target"] or "default"
        _post_hermes(
            organization=subscription.legal_entity.organization,
            payload={
                "event": "mateerp.subscription_reminder",
                "target": target,
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
            },
        )
        return _mark_sent(delivery)
    except (error.URLError, TimeoutError, RuntimeError) as exc:
        return _mark_failed(delivery, exc)
