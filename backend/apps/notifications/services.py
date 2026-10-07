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

from apps.identity.models import (
    LegalEntity,
    Membership,
    MembershipStatus,
    Organization,
    User,
)
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
from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives, get_connection
from django.db.models import F
from django.utils import timezone

from .crypto import decrypt_secret
from .email_templates import get_default_email_template, render_template
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
    html_message: str | None = None,
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
    if html_message:
        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=config["from_email"],
            to=recipients,
            cc=list(cc or []),
            bcc=list(bcc or []),
            connection=connection,
        )
        email.attach_alternative(html_message, "text/html")
    else:
        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=config["from_email"],
            to=recipients,
            cc=list(cc or []),
            bcc=list(bcc or []),
            connection=connection,
        )
    email.send(fail_silently=False)


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
    rule: AlertRule | None = None,
    candidate=None,
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
    rendered = None
    if rule is not None and candidate is not None:
        rendered = _email_render_for_candidate(rule, candidate, destination)
        delivery.alert_rule = rule
        if rendered:
            delivery.email_template = rendered["template"]
            delivery.email_template_version = rendered["template_version"]
            delivery.email_subject = rendered["subject"]
            delivery.email_text_body = rendered["text_body"]
            delivery.email_html_body = rendered["html_body"]
        delivery.save(
            update_fields=[
                "alert_rule",
                "email_template",
                "email_template_version",
                "email_subject",
                "email_text_body",
                "email_html_body",
                "updated_at",
            ]
        )
    try:
        _send_email(
            organization=subscription.legal_entity.organization,
            destination=destination,
            subject=rendered["subject"] if rendered else title,
            message=rendered["text_body"] if rendered else message,
            html_message=rendered["html_body"] if rendered else None,
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
        "schedule_hour": 0,
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
        "schedule_hour": 0,
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
        "schedule_hour": 0,
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
        "schedule_hour": 0,
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
            membership.all_legal_entities or membership.legal_entities.filter(id=entity.id).exists()
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
            subscription.reminder_days if rule.respect_subscription_channels else configured_days
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

    payments = BillingPayment.objects.filter(
        legal_entity=entity,
        paid_on__lte=cutoff,
        expense_payment__isnull=True,
    ).select_related("subscription", "financial_account")
    for payment in payments:
        rows.append(
            AlertCandidate(
                signal=NotificationKind.RECONCILIATION_NEEDED,
                legal_entity=entity,
                source_type="BillingPayment",
                source_id=str(payment.id),
                event_key=f"reconcile-payment:{payment.id}",
                title=f"Payment reconciliation needed: {payment.payment_code}",