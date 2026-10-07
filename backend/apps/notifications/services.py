import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from email.utils import parseaddr
from urllib import error, request
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.db.models import F
from django.utils import timezone

from apps.identity.models import LegalEntity, Membership, MembershipStatus, Organization, User
from apps.identity.policy import Permission, has_permission
from apps.operations.models import (
    BillingInvoiceStatus,
    BillingMode,
    BillingPayment,
    OperationalStatus,
    Subscription,
    SubscriptionBillingPeriod,
    SubscriptionInvoice,
)

from .crypto import decrypt_secret
from .models import (
    AlertFrequency,
    AlertRule,
    DeliveryChannel,
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationIntegrationSettings,
    NotificationKind,
    NotificationSeverity,
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
        "hermes_token_configured": bool(settings.MATEERP_HERMES_WEBHOOK_SECRET),
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


def _smtp_preview_config(organization, proposed: dict) -> dict:
    """Build an SMTP configuration from the unsaved form, without persisting secrets."""
    stored = integration_settings_for(organization)
    previous = integration_settings_payload(organization)
    draft = {**previous, **proposed}

    if not draft["smtp_enabled"]:
        raise RuntimeError("Enable direct email notifications before running the test.")
    if not draft["smtp_host"]:
        raise RuntimeError("Enter an SMTP host before testing.")
    if not draft["smtp_from_email"]:
        raise RuntimeError("Enter a From Email address before testing.")
    if draft["smtp_use_tls"] and draft["smtp_use_ssl"]:
        raise RuntimeError("Choose either TLS or SSL, not both.")

    password = proposed.get("smtp_password")
    if not password:
        password = (
            decrypt_secret(stored.smtp_password_encrypted)
            if stored
            else settings.EMAIL_HOST_PASSWORD
        )
    if draft["smtp_username"] and not password:
        raise RuntimeError("Enter the SMTP mailbox password before testing.")

    from_name = draft["smtp_from_name"]
    from_email = draft["smtp_from_email"]
    return {
        "backend": "django.core.mail.backends.smtp.EmailBackend",
        "host": draft["smtp_host"],
        "port": draft["smtp_port"],
        "username": draft["smtp_username"],
        "password": password,
        "use_tls": draft["smtp_use_tls"],
        "use_ssl": draft["smtp_use_ssl"],
        "from_email": f"{from_name} <{from_email}>" if from_name else from_email,
    }


def _send_email(
    *,
    organization,
    subject: str,
    message: str,
    destination: str | None = None,
    destinations: list[str] | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    config_override: dict | None = None,
) -> None:
    recipients = list(destinations or ([] if destination is None else [destination]))
    if not recipients:
        raise RuntimeError("At least one email recipient is required.")
    config = config_override if config_override is not None else _email_config(organization)
    connection = get_connection(
        backend=config["backend"],
        fail_silently=False,
        host=config["host"],
        port=config["port"],
        username=config["username"],
        password=config["password"],
        use_tls=config["use_tls"],
        use_ssl=config["use_ssl"],
        timeout=15,
    )
    EmailMessage(
        subject=subject,
        body=message,
        from_email=config["from_email"],
        to=recipients,
        cc=list(cc or []),
        bcc=list(bcc or []),
        connection=connection,
    ).send(fail_silently=False)


def send_test_email(*, organization, destination: str, proposed: dict) -> None:
    config = _smtp_preview_config(organization, proposed)
    _send_email(
        organization=organization,
        destination=destination,
        config_override=config,
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
    if not config["token"]:
        raise RuntimeError("Hermes Webhook Secret is not configured in ERP Settings.")
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    timestamp = str(int(time.time()))
    signature = hmac.new(
        config["token"].encode(),
        timestamp.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Timestamp": timestamp,
        "X-Webhook-Signature-V2": signature,
    }

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
            "signal": NotificationKind.RENEWAL_DUE,
            "source_type": "Subscription",
            "source_id": str(subscription.id),
            "channel": channel,
            "destination": destination,
            "reminder_days_before": days_before,
            "due_date": due_date,
            "severity": NotificationSeverity.INFO,
            "title": title,
            "message": message,
            "link": "/operations/subscriptions",
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
            kind=NotificationKind.RENEWAL_DUE,
            severity=severity,
            title=title,
            message=message,
            link="/operations/subscriptions",
            due_date=due_date,
        )
        delivery.severity = severity
        delivery.save(update_fields=["severity", "updated_at"])
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


DEFAULT_ALERT_RULES = (
    {
        "signal": NotificationKind.RENEWAL_DUE,
        "name": "Subscription renewal reminders",
        "severity": NotificationSeverity.INFO,
        "frequency": AlertFrequency.DAILY,
        "schedule_hour": 8,
        "in_app_enabled": True,
        "email_enabled": False,
        "hermes_enabled": False,
        "respect_subscription_channels": True,
        "grace_days": 0,
    },
    {
        "signal": NotificationKind.BUDGET_THRESHOLD,
        "name": "PAYG budget thresholds",
        "severity": NotificationSeverity.WARNING,
        "frequency": AlertFrequency.HOURLY,
        "schedule_hour": 0,
        "in_app_enabled": True,
        "email_enabled": False,
        "hermes_enabled": False,
        "respect_subscription_channels": False,
        "grace_days": 0,
    },
    {
        "signal": NotificationKind.MISSING_INVOICE,
        "name": "Missing vendor invoices",
        "severity": NotificationSeverity.WARNING,
        "frequency": AlertFrequency.DAILY,
        "schedule_hour": 8,
        "in_app_enabled": True,
        "email_enabled": False,
        "hermes_enabled": False,
        "respect_subscription_channels": False,
        "grace_days": 1,
    },
    {
        "signal": NotificationKind.INVOICE_OVERDUE,
        "name": "Overdue vendor invoices",
        "severity": NotificationSeverity.CRITICAL,
        "frequency": AlertFrequency.DAILY,
        "schedule_hour": 8,
        "in_app_enabled": True,
        "email_enabled": False,
        "hermes_enabled": False,
        "respect_subscription_channels": False,
        "grace_days": 0,
    },
    {
        "signal": NotificationKind.RECONCILIATION_NEEDED,
        "name": "Billing reconciliation needed",
        "severity": NotificationSeverity.WARNING,
        "frequency": AlertFrequency.DAILY,
        "schedule_hour": 8,
        "in_app_enabled": True,
        "email_enabled": False,
        "hermes_enabled": False,
        "respect_subscription_channels": False,
        "grace_days": 1,
    },
)


@dataclass
class AlertCandidate:
    signal: str
    legal_entity: object
    source_type: str
    source_id: str
    event_key: str
    title: str
    message: str
    link: str
    severity: str
    due_date: object | None = None
    subscription: object | None = None
    reminder_days_before: int | None = None
    context: dict = field(default_factory=dict)


def ensure_default_alert_rules(organization, *, actor=None) -> list[AlertRule]:
    timezone_name = getattr(organization, "timezone", "") or "UTC"
    rules = []
    for default in DEFAULT_ALERT_RULES:
        defaults = {**default, "schedule_timezone": timezone_name}
        signal = defaults.pop("signal")
        rule, created = AlertRule.objects.get_or_create(
            organization=organization,
            legal_entity=None,
            signal=signal,
            defaults={
                **defaults,
                "created_by": actor,
                "updated_by": actor,
            },
        )
        if created:
            rule.full_clean()
        rules.append(rule)
    return rules


def alert_rule_is_due(rule: AlertRule, *, now=None) -> bool:
    if not rule.enabled:
        return False
    now = now or timezone.now()
    local_now = now.astimezone(ZoneInfo(rule.schedule_timezone))
    if rule.last_evaluated_at is None:
        if rule.frequency == AlertFrequency.DAILY:
            return local_now.hour >= rule.schedule_hour
        return True

    last_local = rule.last_evaluated_at.astimezone(ZoneInfo(rule.schedule_timezone))
    if rule.frequency == AlertFrequency.HOURLY:
        return (last_local.date(), last_local.hour) < (local_now.date(), local_now.hour)
    return last_local.date() < local_now.date() and local_now.hour >= rule.schedule_hour


def _viewers(entity, rule: AlertRule | None = None):
    memberships = Membership.objects.filter(
        organization=entity.organization,
        status=MembershipStatus.ACTIVE,
    ).select_related("user")
    viewers = [
        membership
        for membership in memberships
        if has_permission(membership, Permission.VIEW_NOTIFICATIONS)
        and (
            membership.all_legal_entities
            or membership.legal_entities.filter(id=entity.id).exists()
        )
    ]
    if rule and rule.recipient_user_ids:
        selected = {str(value) for value in rule.recipient_user_ids}
        viewers = [item for item in viewers if str(item.user_id) in selected]
    return viewers


def _invoice_paid_amount(invoice: SubscriptionInvoice) -> Decimal:
    return sum(
        (allocation.amount for allocation in invoice.payment_allocations.all()),
        Decimal("0"),
    )


def _renewal_candidates(rule: AlertRule, entity, today) -> list[AlertCandidate]:
    configured_days = rule.renewal_days or [30, 15, 7, 3, 1, 0]
    max_days = max(configured_days, default=0)
    subscriptions = (
        Subscription.objects.filter(
            legal_entity=entity,
            status=OperationalStatus.ACTIVE,
            next_renewal_date__isnull=False,
            next_renewal_date__gte=today,
            next_renewal_date__lte=today + timedelta(days=max_days),
        )
        .select_related("vendor", "legal_entity__organization")
        .order_by("next_renewal_date", "name")
    )
    rows = []
    for subscription in subscriptions:
        days_remaining = (subscription.next_renewal_date - today).days
        reminder_days = (
            subscription.reminder_days
            if rule.respect_subscription_channels
            else configured_days
        )
        if days_remaining not in reminder_days:
            continue
        if days_remaining <= 3:
            severity = NotificationSeverity.CRITICAL
        elif days_remaining <= 7:
            severity = NotificationSeverity.WARNING
        else:
            severity = rule.severity
        timing = (
            "due today"
            if days_remaining == 0
            else "due tomorrow"
            if days_remaining == 1
            else f"due in {days_remaining} days"
        )
        title = f"Payment reminder: {subscription.name} — {timing}"
        amount = (
            subscription.estimated_cost
            if subscription.billing_mode == BillingMode.PAYG
            else subscription.amount
        )
        message = (
            f"{subscription.name} is {timing} on {subscription.next_renewal_date}. "
            f"{'Estimated cost' if subscription.billing_mode == BillingMode.PAYG else 'Amount'}: "
            f"{amount} {subscription.currency}."
        )
        if subscription.vendor:
            message += f" Vendor: {subscription.vendor.name}."
        if subscription.payment_method:
            message += f" Payment method: {subscription.payment_method}."
        rows.append(
            AlertCandidate(
                signal=NotificationKind.RENEWAL_DUE,
                legal_entity=entity,
                source_type="Subscription",
                source_id=str(subscription.id),
                event_key=f"renewal:{subscription.id}:{subscription.next_renewal_date}:{days_remaining}",
                title=title,
                message=message,
                link="/operations/subscriptions",
                severity=severity,
                due_date=subscription.next_renewal_date,
                subscription=subscription,
                reminder_days_before=days_remaining,
                context={
                    "subscription_code": subscription.subscription_code,
                    "days_remaining": days_remaining,
                    "amount": str(amount),
                    "currency": subscription.currency,
                },
            )
        )
    return rows


def _budget_candidates(rule: AlertRule, entity, today) -> list[AlertCandidate]:
    periods = (
        SubscriptionBillingPeriod.objects.filter(
            legal_entity=entity,
            subscription__status=OperationalStatus.ACTIVE,
            subscription__billing_mode=BillingMode.PAYG,
            subscription__monthly_budget__isnull=False,
            period_start__lte=today,
            period_end__gte=today,
            is_closed=False,
        )
        .select_related("subscription", "subscription__vendor")
        .prefetch_related("invoices")
    )
    rows = []
    for period in periods:
        subscription = period.subscription
        budget = subscription.monthly_budget
        if not budget:
            continue
        actual = sum(
            (
                invoice.total_amount
                for invoice in period.invoices.all()
                if invoice.status != BillingInvoiceStatus.VOID
            ),
            Decimal("0"),
        )
        tracked = max(period.current_usage_amount, actual)
        percent = (tracked / budget * Decimal("100")).quantize(Decimal("0.1"))
        for threshold in subscription.budget_alert_thresholds:
            if percent < Decimal(str(threshold)):
                continue
            severity = (
                NotificationSeverity.CRITICAL
                if threshold >= 100
                else NotificationSeverity.WARNING
                if threshold >= 80
                else rule.severity
            )
            title = f"Budget alert: {subscription.name} reached {threshold}%"
            message = (
                f"{subscription.name} is at {percent}% of its {budget} {subscription.currency} "
                f"monthly budget. Current tracked cost: {tracked} {subscription.currency}."
            )
            rows.append(
                AlertCandidate(
                    signal=NotificationKind.BUDGET_THRESHOLD,
                    legal_entity=entity,
                    source_type="SubscriptionBillingPeriod",
                    source_id=str(period.id),
                    event_key=f"budget:{period.id}:{threshold}",
                    title=title,
                    message=message,
                    link=f"/operations/billing?subscription={subscription.id}",
                    severity=severity,
                    due_date=period.period_end,
                    subscription=subscription,
                    context={
                        "subscription_code": subscription.subscription_code,
                        "threshold_percent": threshold,
                        "budget_percent": str(percent),
                        "budget": str(budget),
                        "tracked_cost": str(tracked),
                        "currency": subscription.currency,
                    },
                )
            )
    return rows


def _missing_invoice_candidates(rule: AlertRule, entity, today) -> list[AlertCandidate]:
    cutoff = today - timedelta(days=rule.grace_days)
    periods = (
        SubscriptionBillingPeriod.objects.filter(
            legal_entity=entity,
            subscription__status=OperationalStatus.ACTIVE,
            period_end__lt=cutoff,
            is_closed=False,
        )
        .select_related("subscription", "subscription__vendor")
        .prefetch_related("invoices")
    )
    rows = []
    for period in periods:
        if any(invoice.status != BillingInvoiceStatus.VOID for invoice in period.invoices.all()):
            continue
        subscription = period.subscription
        title = f"Missing invoice: {subscription.name}"
        message = (
            f"No vendor invoice is recorded for {subscription.name} billing period "
            f"{period.period_start} to {period.period_end}. "
            f"The period ended {(today - period.period_end).days} days ago."
        )
        rows.append(
            AlertCandidate(
                signal=NotificationKind.MISSING_INVOICE,
                legal_entity=entity,
                source_type="SubscriptionBillingPeriod",
                source_id=str(period.id),
                event_key=f"missing-invoice:{period.id}",
                title=title,
                message=message,
                link=f"/operations/billing?subscription={subscription.id}",
                severity=rule.severity,
                due_date=period.period_end,
                subscription=subscription,
                context={
                    "subscription_code": subscription.subscription_code,
                    "period_start": str(period.period_start),
                    "period_end": str(period.period_end),
                },
            )
        )
    return rows


def _overdue_invoice_candidates(rule: AlertRule, entity, today) -> list[AlertCandidate]:
    cutoff = today - timedelta(days=rule.grace_days)
    invoices = (
        SubscriptionInvoice.objects.filter(
            legal_entity=entity,
            due_date__isnull=False,
            due_date__lte=cutoff,
        )
        .exclude(status__in=[BillingInvoiceStatus.PAID, BillingInvoiceStatus.VOID])
        .select_related("billing_period__subscription", "vendor")
        .prefetch_related("payment_allocations")
    )
    rows = []
    for invoice in invoices:
        paid = _invoice_paid_amount(invoice)
        outstanding = max(invoice.total_amount - paid, Decimal("0"))
        if outstanding <= 0:
            continue
        subscription = invoice.billing_period.subscription
        overdue_days = (today - invoice.due_date).days
        severity = NotificationSeverity.CRITICAL if overdue_days >= 7 else rule.severity
        title = f"Invoice overdue: {invoice.invoice_number}"
        message = (
            f"{invoice.vendor.name} invoice {invoice.invoice_number} for {subscription.name} "
            f"has {outstanding} {invoice.currency} outstanding and is {overdue_days} days overdue."
        )
        rows.append(
            AlertCandidate(
                signal=NotificationKind.INVOICE_OVERDUE,
                legal_entity=entity,
                source_type="SubscriptionInvoice",
                source_id=str(invoice.id),
                event_key=f"invoice-overdue:{invoice.id}",
                title=title,
                message=message,
                link=f"/operations/billing?subscription={subscription.id}",
                severity=severity,
                due_date=invoice.due_date,
                subscription=subscription,
                context={
                    "invoice_number": invoice.invoice_number,
                    "outstanding": str(outstanding),
                    "currency": invoice.currency,
                    "overdue_days": overdue_days,
                },
            )
        )
    return rows


def _reconciliation_candidates(rule: AlertRule, entity, today) -> list[AlertCandidate]:
    cutoff = today - timedelta(days=rule.grace_days)
    rows = []
    invoices = (
        SubscriptionInvoice.objects.filter(
            legal_entity=entity,
            invoice_date__lte=cutoff,
        )
        .exclude(status=BillingInvoiceStatus.VOID)
        .select_related("billing_period__subscription", "vendor", "expense")
    )
    for invoice in invoices:
        mismatch = (
            invoice.expense_id is None
            or invoice.expense.currency != invoice.currency
            or invoice.expense.amount != invoice.total_amount
        )
        if not mismatch:
            continue
        subscription = invoice.billing_period.subscription
        reason = (
            "no accounting expense is linked"
            if invoice.expense_id is None
            else "the linked accounting expense amount or currency does not match"
        )
        rows.append(
            AlertCandidate(
                signal=NotificationKind.RECONCILIATION_NEEDED,
                legal_entity=entity,
                source_type="SubscriptionInvoice",
                source_id=str(invoice.id),
                event_key=f"reconcile-invoice:{invoice.id}",
                title=f"Invoice reconciliation needed: {invoice.invoice_number}",
                message=(
                    f"{invoice.vendor.name} invoice {invoice.invoice_number} needs reconciliation: "
                    f"{reason}."
                ),
                link=f"/operations/billing?subscription={subscription.id}",
                severity=rule.severity,
                due_date=invoice.invoice_date,
                subscription=subscription,
                context={
                    "invoice_number": invoice.invoice_number,
                    "reason": reason,
                    "amount": str(invoice.total_amount),
                    "currency": invoice.currency,
                },
            )
        )

    payments = (
        BillingPayment.objects.filter(
            legal_entity=entity,
            paid_on__lte=cutoff,
            expense_payment__isnull=True,
        )
        .select_related("subscription", "financial_account")
    )
    for payment in payments:
        rows.append(
            AlertCandidate(
                signal=NotificationKind.RECONCILIATION_NEEDED,
                legal_entity=entity,
                source_type="BillingPayment",
                source_id=str(payment.id),
                event_key=f"reconcile-payment:{payment.id}",
                title=f"Payment reconciliation needed: {payment.payment_code}",
                message=(
                    f"{payment.payment_code} for {payment.subscription.name} has not been matched "
                    f"to an accounting expense payment. Amount: {payment.amount} {payment.currency}."
                ),
                link=f"/operations/billing?subscription={payment.subscription_id}",
                severity=rule.severity,
                due_date=payment.paid_on,
                subscription=payment.subscription,
                context={
                    "payment_code": payment.payment_code,
                    "amount": str(payment.amount),
                    "currency": payment.currency,
                },
            )
        )
    return rows


def _candidates_for_rule(rule: AlertRule, entity, today) -> list[AlertCandidate]:
    if rule.signal == NotificationKind.RENEWAL_DUE:
        return _renewal_candidates(rule, entity, today)
    if rule.signal == NotificationKind.BUDGET_THRESHOLD:
        return _budget_candidates(rule, entity, today)
    if rule.signal == NotificationKind.MISSING_INVOICE:
        return _missing_invoice_candidates(rule, entity, today)
    if rule.signal == NotificationKind.INVOICE_OVERDUE:
        return _overdue_invoice_candidates(rule, entity, today)
    if rule.signal == NotificationKind.RECONCILIATION_NEEDED:
        return _reconciliation_candidates(rule, entity, today)
    return []


def _notification_key(rule: AlertRule, candidate: AlertCandidate) -> str:
    return f"alert:{rule.id}:{candidate.event_key}"[:180]


def _rule_delivery(
    *,
    rule: AlertRule,
    candidate: AlertCandidate,
    channel: str,
    destination: str,
) -> NotificationDelivery:
    notification_key = _notification_key(rule, candidate)
    raw = f"{rule.id}:{candidate.event_key}:{channel}:{destination or 'default'}"
    delivery_key = f"alert:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"
    delivery, _ = NotificationDelivery.objects.get_or_create(
        delivery_key=delivery_key,
        defaults={
            "organization": rule.organization,
            "legal_entity": candidate.legal_entity,
            "subscription": candidate.subscription,
            "alert_rule": rule,
            "signal": candidate.signal,
            "source_type": candidate.source_type,
            "source_id": candidate.source_id,
            "channel": channel,
            "destination": destination,
            "reminder_days_before": candidate.reminder_days_before,
            "due_date": candidate.due_date,
            "severity": candidate.severity,
            "title": candidate.title,
            "message": candidate.message,
            "link": candidate.link,
            "context": {
                **candidate.context,
                "notification_key": notification_key,
                "event_key": candidate.event_key,
            },
        },
    )
    return delivery


def _attempt_rule_delivery(
    *,
    delivery: NotificationDelivery,
    recipient=None,
) -> NotificationDelivery:
    if delivery.status == DeliveryStatus.SENT:
        return delivery
    try:
        if delivery.channel == DeliveryChannel.IN_APP:
            if recipient is None:
                recipient = User.objects.filter(email__iexact=delivery.destination).first()
            if recipient is None:
                raise RuntimeError("In-app notification recipient no longer exists.")
            dedupe_key = delivery.context.get("notification_key") or delivery.delivery_key
            upsert_notification(
                organization=delivery.organization,
                legal_entity=delivery.legal_entity,
                recipient=recipient,
                dedupe_key=dedupe_key,
                kind=delivery.signal,
                severity=delivery.severity,
                title=delivery.title,
                message=delivery.message,
                link=delivery.link,
                due_date=delivery.due_date,
            )
        elif delivery.channel == DeliveryChannel.EMAIL:
            _send_email(
                organization=delivery.organization,
                destination=delivery.destination,
                subject=delivery.title,
                message=delivery.message,
            )
        elif delivery.channel == DeliveryChannel.HERMES:
            config = _hermes_config(delivery.organization)
            target = delivery.destination or config["default_target"] or "default"
            _post_hermes(
                organization=delivery.organization,
                payload={
                    "event": "mateerp.alert",
                    "target": target,
                    "signal": delivery.signal,
                    "title": delivery.title,
                    "message": delivery.message,
                    "source": {
                        "type": delivery.source_type,
                        "id": delivery.source_id,
                    },
                    "context": delivery.context,
                },
            )
        else:
            raise RuntimeError("Unsupported alert delivery channel.")
        return _mark_sent(delivery)
    except Exception as exc:
        return _mark_failed(delivery, exc)


def retry_notification_delivery(delivery: NotificationDelivery) -> NotificationDelivery:
    if delivery.status == DeliveryStatus.SENT:
        return delivery
    return _attempt_rule_delivery(delivery=delivery)


def dismiss_notification(notification: Notification) -> Notification:
    if notification.resolved_at is None:
        notification.resolved_at = timezone.now()
        notification.save(update_fields=["resolved_at", "updated_at"])
    return notification


def _deliver_candidate(rule: AlertRule, candidate: AlertCandidate, viewers):
    deliveries = []
    active_notification_keys = []

    if candidate.signal == NotificationKind.RENEWAL_DUE and rule.respect_subscription_channels:
        subscription = candidate.subscription
        if subscription.reminder_in_app:
            for membership in viewers:
                delivery = deliver_in_app(
                    subscription=subscription,
                    recipient=membership.user,
                    days_before=candidate.reminder_days_before,
                    due_date=candidate.due_date,
                    severity=candidate.severity,
                    title=candidate.title,
                    message=candidate.message,
                )
                if delivery.alert_rule_id is None:
                    delivery.alert_rule = rule
                    delivery.save(update_fields=["alert_rule", "updated_at"])
                deliveries.append(delivery)
                active_notification_keys.append(delivery.delivery_key)

        if subscription.reminder_email:
            recipients = subscription.reminder_email_recipients or [
                membership.user.email for membership in viewers
            ]
            for destination in dict.fromkeys(recipients):
                delivery = deliver_email(
                    subscription=subscription,
                    destination=destination,
                    days_before=candidate.reminder_days_before,
                    due_date=candidate.due_date,
                    title=candidate.title,
                    message=candidate.message,
                )
                if delivery.alert_rule_id is None:
                    delivery.alert_rule = rule
                    delivery.save(update_fields=["alert_rule", "updated_at"])
                deliveries.append(delivery)

        if subscription.reminder_hermes:
            delivery = deliver_hermes(
                subscription=subscription,
                destination=subscription.hermes_target or rule.hermes_target or "default",
                days_before=candidate.reminder_days_before,
                due_date=candidate.due_date,
                title=candidate.title,
                message=candidate.message,
            )
            if delivery.alert_rule_id is None:
                delivery.alert_rule = rule
                delivery.save(update_fields=["alert_rule", "updated_at"])
            deliveries.append(delivery)
        return deliveries, active_notification_keys

    if rule.in_app_enabled:
        for membership in viewers:
            delivery = _rule_delivery(
                rule=rule,
                candidate=candidate,
                channel=DeliveryChannel.IN_APP,
                destination=membership.user.email,
            )
            deliveries.append(
                _attempt_rule_delivery(delivery=delivery, recipient=membership.user)
            )
            active_notification_keys.append(_notification_key(rule, candidate))

    if rule.email_enabled:
        recipients = rule.email_recipients or [
            membership.user.email for membership in viewers
        ]
        for destination in dict.fromkeys(recipients):
            delivery = _rule_delivery(
                rule=rule,
                candidate=candidate,
                channel=DeliveryChannel.EMAIL,
                destination=destination,
            )
            deliveries.append(_attempt_rule_delivery(delivery=delivery))

    if rule.hermes_enabled:
        delivery = _rule_delivery(
            rule=rule,
            candidate=candidate,
            channel=DeliveryChannel.HERMES,
            destination=rule.hermes_target or "default",
        )
        deliveries.append(_attempt_rule_delivery(delivery=delivery))

    return deliveries, active_notification_keys


def _resolve_stale_rule_notifications(rule: AlertRule, entity, active_keys):
    queryset = Notification.objects.filter(
        organization=rule.organization,
        legal_entity=entity,
        kind=rule.signal,
        resolved_at__isnull=True,
        dedupe_key__startswith=f"alert:{rule.id}:",
    )
    if active_keys:
        queryset = queryset.exclude(dedupe_key__in=set(active_keys))
    resolve_notifications(queryset)


def _resolve_stale_renewal_notifications(entity, viewers):
    valid_deliveries = NotificationDelivery.objects.filter(
        legal_entity=entity,
        channel=DeliveryChannel.IN_APP,
        signal=NotificationKind.RENEWAL_DUE,
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
        ).exclude(dedupe_key__startswith="alert:")
        if valid_keys:
            stale = stale.exclude(dedupe_key__in=valid_keys)
        resolve_notifications(stale)


def evaluate_alert_rule(rule: AlertRule, *, entities=None, now=None) -> dict:
    now = now or timezone.now()
    today = now.astimezone(ZoneInfo(rule.schedule_timezone)).date()
    entities = list(
        entities
        if entities is not None
        else LegalEntity.objects.filter(
            organization=rule.organization,
            status="ACTIVE",
        )
    )
    sent = 0
    failed = 0
    active_events = 0
    try:
        for entity in entities:
            viewers = _viewers(entity, rule)
            candidates = _candidates_for_rule(rule, entity, today)
            active_events += len(candidates)
            active_keys = []
            for candidate in candidates:
                deliveries, keys = _deliver_candidate(rule, candidate, viewers)
                active_keys.extend(keys)
                for delivery in deliveries:
                    if delivery.status == DeliveryStatus.SENT:
                        sent += 1
                    elif delivery.status == DeliveryStatus.FAILED:
                        failed += 1
            if rule.signal == NotificationKind.RENEWAL_DUE and rule.respect_subscription_channels:
                _resolve_stale_renewal_notifications(entity, viewers)
            else:
                _resolve_stale_rule_notifications(rule, entity, active_keys)
        rule.last_error = ""
    except Exception as exc:
        rule.last_error = str(exc)[:2000]
        failed += 1
    rule.last_evaluated_at = now
    rule.last_delivery_count = sent
    rule.last_failure_count = failed
    rule.save(
        update_fields=[
            "last_evaluated_at",
            "last_delivery_count",
            "last_failure_count",
            "last_error",
            "updated_at",
        ]
    )
    return {
        "rule_id": str(rule.id),
        "signal": rule.signal,
        "active_events": active_events,
        "sent": sent,
        "failed": failed,
        "error": rule.last_error,
    }


def run_alert_rules(
    *,
    organization=None,
    legal_entity=None,
    force=False,
    now=None,
) -> dict:
    now = now or timezone.now()
    organizations = (
        [organization]
        if organization is not None
        else list(Organization.objects.filter(status="ACTIVE"))
    )
    results = []
    skipped = 0
    for current_org in organizations:
        ensure_default_alert_rules(current_org)
        rules = list(
            AlertRule.objects.filter(organization=current_org)
            .select_related("organization", "legal_entity")
            .order_by("signal", "legal_entity_id")
        )
        entity_overrides = {
            (rule.legal_entity_id, rule.signal)
            for rule in rules
            if rule.legal_entity_id is not None
        }

        for rule in rules:
            if not rule.enabled:
                skipped += 1
                continue
            if not force and not alert_rule_is_due(rule, now=now):
                skipped += 1
                continue

            if rule.legal_entity_id:
                if legal_entity is not None and rule.legal_entity_id != legal_entity.id:
                    continue
                targets = [rule.legal_entity]
            else:
                targets = list(
                    LegalEntity.objects.filter(
                        organization=current_org,
                        status="ACTIVE",
                    )
                )
                if legal_entity is not None:
                    targets = [item for item in targets if item.id == legal_entity.id]
                targets = [
                    item
                    for item in targets
                    if (item.id, rule.signal) not in entity_overrides
                ]
            results.append(evaluate_alert_rule(rule, entities=targets, now=now))

    return {
        "rules_evaluated": len(results),
        "rules_skipped": skipped,
        "active_events": sum(row["active_events"] for row in results),
        "deliveries_sent": sum(row["sent"] for row in results),
        "deliveries_failed": sum(row["failed"] for row in results),
        "results": results,
    }

