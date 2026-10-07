import base64
import calendar
import ipaddress
import json
import socket
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib import error, parse, request
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_audit_event
from apps.identity.models import LegalEntity, Organization
from apps.notifications.crypto import decrypt_secret
from apps.notifications.services import run_alert_rules
from apps.operations.models import (
    BillingMode,
    OperationalStatus,
    Subscription,
    SubscriptionBillingPeriod,
)

from .models import (
    AutomationFrequency,
    AutomationKind,
    AutomationPolicy,
    AutomationRun,
    RunStatus,
    RunTrigger,
    SyncStatus,
    VendorAuthType,
    VendorIntegration,
    VendorSyncRun,
)

MAX_VENDOR_RESPONSE_BYTES = 2 * 1024 * 1024


class VendorIntegrationError(RuntimeError):
    pass


class _NoRedirectHandler(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise VendorIntegrationError("Vendor API redirects are not allowed.")


def _validate_public_https_url(value: str) -> str:
    parsed = parse.urlparse(value)
    if parsed.scheme.lower() != "https":
        raise VendorIntegrationError("Vendor API endpoint must use HTTPS.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise VendorIntegrationError("Vendor API endpoint is invalid.")
    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
        raise VendorIntegrationError("Local vendor API endpoints are not allowed.")
    try:
        addresses = socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise VendorIntegrationError("Vendor API hostname could not be resolved.") from exc
    for item in addresses:
        address = ipaddress.ip_address(item[4][0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            raise VendorIntegrationError("Vendor API endpoint resolves to a non-public address.")
    return value


def _json_path(data, path: str):
    value = data
    for part in [item for item in path.strip().split(".") if item]:
        if isinstance(value, list):
            try:
                value = value[int(part)]
            except (ValueError, IndexError) as exc:
                raise VendorIntegrationError(f"JSON path '{path}' was not found.") from exc
        elif isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise VendorIntegrationError(f"JSON path '{path}' was not found.")
    return value


def _decimal_value(value, label: str, quantize: str) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal(quantize))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise VendorIntegrationError(f"{label} is not a valid number.") from exc
    if amount < 0:
        raise VendorIntegrationError(f"{label} cannot be negative.")
    return amount


def _request_headers(config: dict) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "MateERP-VendorSync/1.0",
    }
    for key, value in (config.get("custom_headers") or {}).items():
        headers[str(key)] = str(value)

    auth_type = config.get("auth_type") or VendorAuthType.NONE
    secret = config.get("secret") or ""
    if auth_type == VendorAuthType.BEARER:
        if not secret:
            raise VendorIntegrationError("Bearer authentication requires a token.")
        headers["Authorization"] = f"Bearer {secret}"
    elif auth_type == VendorAuthType.API_KEY_HEADER:
        if not secret:
            raise VendorIntegrationError("API key authentication requires a secret.")
        headers[config.get("api_key_header") or "X-API-Key"] = secret
    elif auth_type == VendorAuthType.BASIC:
        username = config.get("auth_username") or ""
        if not username or not secret:
            raise VendorIntegrationError("Basic authentication requires username and password.")
        token = base64.b64encode(f"{username}:{secret}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    return headers


def fetch_vendor_payload(config: dict) -> tuple[object, int]:
    endpoint = _validate_public_https_url(config["endpoint_url"])
    req = request.Request(endpoint, headers=_request_headers(config), method="GET")
    opener = request.build_opener(_NoRedirectHandler())
    try:
        with opener.open(req, timeout=int(config.get("timeout_seconds") or 15)) as response:
            status = int(response.status)
            raw = response.read(MAX_VENDOR_RESPONSE_BYTES + 1)
    except VendorIntegrationError:
        raise
    except error.HTTPError as exc:
        raise VendorIntegrationError(f"Vendor API returned HTTP {exc.code}.") from exc
    except (error.URLError, TimeoutError, OSError) as exc:
        raise VendorIntegrationError("Could not connect to the vendor API.") from exc
    if len(raw) > MAX_VENDOR_RESPONSE_BYTES:
        raise VendorIntegrationError("Vendor API response exceeded the 2 MB safety limit.")
    try:
        return json.loads(raw.decode("utf-8")), status
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VendorIntegrationError("Vendor API did not return valid JSON.") from exc


def extract_vendor_usage(config: dict, payload, *, subscription) -> dict:
    cost = _decimal_value(
        _json_path(payload, config["cost_json_path"]),
        "Cost amount",
        "0.01",
    )
    quantity = None
    if config.get("usage_quantity_json_path"):
        quantity = _decimal_value(
            _json_path(payload, config["usage_quantity_json_path"]),
            "Usage quantity",
            "0.0001",
        )
    currency = subscription.currency
    if config.get("currency_json_path"):
        currency = str(_json_path(payload, config["currency_json_path"])).strip().upper()
    if currency != subscription.currency:
        raise VendorIntegrationError(
            f"Vendor returned {currency}, but the subscription currency is {subscription.currency}."
        )
    usage_unit = subscription.usage_unit
    if config.get("usage_unit_json_path"):
        usage_unit = str(_json_path(payload, config["usage_unit_json_path"])).strip()[:40]
    return {
        "cost_amount": cost,
        "usage_quantity": quantity,
        "currency": currency,
        "usage_unit": usage_unit,
    }


def integration_config(integration: VendorIntegration) -> dict:
    return {
        "endpoint_url": integration.endpoint_url,
        "auth_type": integration.auth_type,
        "auth_username": integration.auth_username,
        "secret": decrypt_secret(integration.secret_encrypted),
        "api_key_header": integration.api_key_header,
        "custom_headers": integration.custom_headers,
        "cost_json_path": integration.cost_json_path,
        "usage_quantity_json_path": integration.usage_quantity_json_path,
        "currency_json_path": integration.currency_json_path,
        "usage_unit_json_path": integration.usage_unit_json_path,
        "timeout_seconds": integration.timeout_seconds,
    }


def test_vendor_configuration(*, config: dict, subscription) -> dict:
    payload, http_status = fetch_vendor_payload(config)
    extracted = extract_vendor_usage(config, payload, subscription=subscription)
    return {"http_status": http_status, **extracted}


def _month_bounds(entity, *, now=None) -> tuple[date, date]:
    now = now or timezone.now()
    local_date = now.astimezone(ZoneInfo(entity.timezone)).date()
    last_day = calendar.monthrange(local_date.year, local_date.month)[1]
    return local_date.replace(day=1), local_date.replace(day=last_day)


@transaction.atomic
def ensure_current_billing_period(subscription, *, actor=None, now=None):
    start, end = _month_bounds(subscription.legal_entity, now=now)
    period, created = SubscriptionBillingPeriod.objects.get_or_create(
        subscription=subscription,
        period_start=start,
        period_end=end,
        defaults={
            "legal_entity": subscription.legal_entity,
            "estimated_cost": subscription.estimated_cost,
            "current_usage_amount": Decimal("0"),
            "usage_unit": subscription.usage_unit,
            "created_by": actor,
            "notes": "Automatically created by MateERP automation.",
        },
    )
    return period, created


def sync_vendor_integration(
    integration: VendorIntegration,
    *,
    trigger=RunTrigger.MANUAL,
    actor=None,
    request_obj=None,
) -> VendorSyncRun:
    run = VendorSyncRun.objects.create(
        integration=integration,
        trigger=trigger,
        initiated_by=actor,
    )
    now = timezone.now()
    try:
        if not integration.enabled:
            raise VendorIntegrationError("Vendor integration is disabled.")
        subscription = Subscription.objects.select_related("legal_entity", "vendor").get(
            pk=integration.subscription_id
        )
        if subscription.status != OperationalStatus.ACTIVE:
            raise VendorIntegrationError("Subscription is not active.")
        if subscription.billing_mode != BillingMode.PAYG:
            raise VendorIntegrationError("Vendor sync requires a PAYG subscription.")

        config = integration_config(integration)
        payload, http_status = fetch_vendor_payload(config)
        extracted = extract_vendor_usage(
            config,
            payload,
            subscription=subscription,
        )

        with transaction.atomic():
            start_date, end_date = _month_bounds(subscription.legal_entity, now=now)
            period = SubscriptionBillingPeriod.objects.select_for_update().filter(
                subscription=subscription,
                period_start=start_date,
                period_end=end_date,
            ).first()
            if period is None:
                if not integration.auto_create_period:
                    raise VendorIntegrationError(
                        "No current billing period exists and automatic creation is disabled."
                    )
                period, _ = ensure_current_billing_period(
                    subscription,
                    actor=actor,
                    now=now,
                )
            if period.is_closed:
                raise VendorIntegrationError("Current billing period is closed.")

            period.current_usage_amount = extracted["cost_amount"]
            period.usage_quantity = extracted["usage_quantity"]
            if extracted["usage_unit"]:
                period.usage_unit = extracted["usage_unit"]
            period.current_usage_updated_at = now
            period.save()

            record_audit_event(
                actor=actor,
                organization=integration.organization,
                legal_entity=integration.legal_entity,
                action="automation.vendor_usage_synced",
                object_type="VendorIntegration",
                object_id=integration.id,
                new_state={
                    "subscription_id": str(subscription.id),
                    "billing_period_id": str(period.id),
                    "cost_amount": str(extracted["cost_amount"]),
                    "usage_quantity": (
                        str(extracted["usage_quantity"])
                        if extracted["usage_quantity"] is not None
                        else None
                    ),
                    "currency": extracted["currency"],
                },
                request=request_obj,
            )

        run.status = RunStatus.SUCCESS
        run.http_status = http_status
        run.billing_period = period
        run.cost_amount = extracted["cost_amount"]
        run.usage_quantity = extracted["usage_quantity"]
        run.currency = extracted["currency"]
        run.usage_unit = extracted["usage_unit"]
        integration.last_sync_at = now
        integration.last_sync_status = SyncStatus.SUCCESS
        integration.last_sync_error = ""
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error = str(exc)[:2000]
        integration.last_sync_at = now
        integration.last_sync_status = SyncStatus.FAILED
        integration.last_sync_error = run.error

    run.finished_at = timezone.now()
    run.save()
    integration.save(
        update_fields=[
            "last_sync_at",
            "last_sync_status",
            "last_sync_error",
            "updated_at",
        ]
    )
    return run


def ensure_default_automation_policies(organization, *, actor=None):
    timezone_name = organization.timezone or "UTC"
    defaults = (
        (
            AutomationKind.ENSURE_PAYG_PERIODS,
            "Ensure monthly PAYG billing periods",
            AutomationFrequency.DAILY,
            True,
        ),
        (
            AutomationKind.SYNC_VENDOR_USAGE,
            "Sync vendor PAYG usage",
            AutomationFrequency.HOURLY,
            True,
        ),
        (
            AutomationKind.REFRESH_ALERTS,
            "Refresh operational alert rules",
            AutomationFrequency.DAILY,
            False,
        ),
    )
    result = []
    for kind, name, frequency, enabled in defaults:
        policy, _ = AutomationPolicy.objects.get_or_create(
            organization=organization,
            legal_entity=None,
            kind=kind,
            defaults={
                "name": name,
                "frequency": frequency,
                "enabled": enabled,
                "schedule_hour": 0,
                "schedule_timezone": timezone_name,
                "created_by": actor,
                "updated_by": actor,
            },
        )
        result.append(policy)
    return result


def automation_policy_is_due(policy, *, now=None):
    if not policy.enabled:
        return False
    now = now or timezone.now()
    local_now = now.astimezone(ZoneInfo(policy.schedule_timezone))
    if policy.last_run_at is None:
        return (
            policy.frequency == AutomationFrequency.HOURLY or local_now.hour >= policy.schedule_hour
        )
    last_local = policy.last_run_at.astimezone(ZoneInfo(policy.schedule_timezone))
    if policy.frequency == AutomationFrequency.HOURLY:
        return (last_local.date(), last_local.hour) < (local_now.date(), local_now.hour)
    return last_local.date() < local_now.date() and local_now.hour >= policy.schedule_hour


def _target_entities(policy):
    if policy.legal_entity_id:
        return [policy.legal_entity]
    override_entity_ids = AutomationPolicy.objects.filter(
        organization=policy.organization,
        kind=policy.kind,
        legal_entity__isnull=False,
    ).values_list("legal_entity_id", flat=True)
    return list(
        LegalEntity.objects.filter(
            organization=policy.organization,
            status="ACTIVE",
        ).exclude(id__in=override_entity_ids)
    )


def _ensure_periods(policy, *, actor=None):
    created = 0
    existing = 0
    for entity in _target_entities(policy):
        subscriptions = Subscription.objects.filter(
            legal_entity=entity,
            status=OperationalStatus.ACTIVE,
            billing_mode=BillingMode.PAYG,
        ).select_related("legal_entity")
        for subscription in subscriptions:
            _, was_created = ensure_current_billing_period(subscription, actor=actor)
            if was_created:
                created += 1
            else:
                existing += 1
    return {"created": created, "already_present": existing}


def _sync_integrations(policy, *, actor=None):
    queryset = VendorIntegration.objects.filter(
        organization=policy.organization,
        enabled=True,
    ).select_related("subscription", "legal_entity", "vendor")
    if policy.legal_entity_id:
        queryset = queryset.filter(legal_entity=policy.legal_entity)
    success = 0
    failed = 0
    for integration in queryset:
        run = sync_vendor_integration(
            integration,
            trigger=RunTrigger.SCHEDULED,
            actor=actor,
        )
        if run.status == RunStatus.SUCCESS:
            success += 1
        else:
            failed += 1
    return {"integrations": queryset.count(), "success": success, "failed": failed}


def _refresh_alerts(policy):
    result = run_alert_rules(
        organization=policy.organization,
        legal_entity=policy.legal_entity,
        force=True,
    )
    return {
        "rules_evaluated": result["rules_evaluated"],
        "active_events": result["active_events"],
        "deliveries_sent": result["deliveries_sent"],
        "deliveries_failed": result["deliveries_failed"],
    }


def run_automation_policy(
    policy: AutomationPolicy,
    *,
    trigger=RunTrigger.MANUAL,
    actor=None,
    request_obj=None,
) -> AutomationRun:
    run = AutomationRun.objects.create(
        policy=policy,
        trigger=trigger,
        initiated_by=actor,
    )
    try:
        if policy.kind == AutomationKind.ENSURE_PAYG_PERIODS:
            with transaction.atomic():
                summary = _ensure_periods(policy, actor=actor)
        elif policy.kind == AutomationKind.SYNC_VENDOR_USAGE:
            summary = _sync_integrations(policy, actor=actor)
        elif policy.kind == AutomationKind.REFRESH_ALERTS:
            summary = _refresh_alerts(policy)
        else:
            raise RuntimeError("Unsupported automation policy.")
        run.status = RunStatus.SUCCESS
        run.summary = summary
        policy.last_status = RunStatus.SUCCESS
        policy.last_summary = summary
        policy.last_error = ""
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.error = str(exc)[:2000]
        policy.last_status = RunStatus.FAILED
        policy.last_summary = {}
        policy.last_error = run.error
    now = timezone.now()
    run.finished_at = now
    policy.last_run_at = now
    run.save()
    policy.save(
        update_fields=[
            "last_run_at",
            "last_status",
            "last_summary",
            "last_error",
            "updated_at",
        ]
    )
    record_audit_event(
        actor=actor,
        organization=policy.organization,
        legal_entity=policy.legal_entity,
        action="automation.policy_run",
        object_type="AutomationPolicy",
        object_id=policy.id,
        new_state={
            "kind": policy.kind,
            "status": run.status,
            "summary": run.summary,
        },
        request=request_obj,
    )
    return run


def run_due_automations(*, now=None):
    now = now or timezone.now()
    policies = []
    for organization in Organization.objects.filter(status="ACTIVE"):
        ensure_default_automation_policies(organization)
        policies.extend(
            AutomationPolicy.objects.filter(
                organization=organization,
                enabled=True,
            ).select_related("organization", "legal_entity")
        )
    executed = 0
    failed = 0
    skipped = 0
    for policy in policies:
        if not automation_policy_is_due(policy, now=now):
            skipped += 1
            continue
        run = run_automation_policy(
            policy,
            trigger=RunTrigger.SCHEDULED,
        )
        executed += 1
        if run.status == RunStatus.FAILED:
            failed += 1
    return {"executed": executed, "failed": failed, "skipped": skipped}
