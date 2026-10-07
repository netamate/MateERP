from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.test import Client

from apps.automation.models import (
    AutomationKind,
    AutomationPolicy,
    RunStatus,
    RunTrigger,
    SyncStatus,
    VendorIntegration,
)
from apps.automation.services import (
    VendorIntegrationError,
    ensure_default_automation_policies,
    fetch_vendor_payload,
    run_automation_policy,
    sync_vendor_integration,
)
from apps.finance.models import Expense, Vendor
from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.operations.models import (
    BillingMode,
    Subscription,
    SubscriptionBillingPeriod,
    SubscriptionInvoice,
)


def signed_in_owner(email="automation-owner@example.com"):
    owner = User.objects.create_user(email=email, password="test-pass-123")
    organization, entity, membership = create_organization_with_owner(
        owner=owner,
        name=f"Automation {email}",
        base_currency="USD",
    )
    client = Client()
    client.force_login(owner)
    session = client.session
    session["active_organization_id"] = str(organization.id)
    session["active_legal_entity_id"] = str(entity.id)
    session.save()
    return client, owner, organization, entity, membership


def payg_subscription(entity):
    vendor = Vendor.objects.create(
        legal_entity=entity,
        code="CLOUD",
        name="Cloud Vendor",
    )
    subscription = Subscription.objects.create(
        legal_entity=entity,
        vendor=vendor,
        name="Cloud PAYG",
        billing_mode=BillingMode.PAYG,
        estimated_cost=Decimal("20.00"),
        monthly_budget=Decimal("100.00"),
        usage_unit="GB",
        amount=Decimal("0"),
        currency="USD",
    )
    return vendor, subscription


@pytest.mark.django_db
def test_vendor_sync_updates_current_payg_period_without_financial_posting(monkeypatch):
    _, owner, organization, entity, _ = signed_in_owner()
    vendor, subscription = payg_subscription(entity)
    integration = VendorIntegration.objects.create(
        organization=organization,
        legal_entity=entity,
        vendor=vendor,
        subscription=subscription,
        name="Cloud Usage",
        endpoint_url="https://api.vendor.example/usage",
        cost_json_path="data.cost",
        usage_quantity_json_path="data.quantity",
        currency_json_path="data.currency",
        usage_unit_json_path="data.unit",
        created_by=owner,
        updated_by=owner,
    )

    monkeypatch.setattr(
        "apps.automation.services.fetch_vendor_payload",
        lambda config: (
            {
                "data": {
                    "cost": "42.35",
                    "quantity": "128.5000",
                    "currency": "USD",
                    "unit": "GB",
                }
            },
            200,
        ),
    )

    run = sync_vendor_integration(
        integration,
        trigger=RunTrigger.MANUAL,
        actor=owner,
    )

    assert run.status == RunStatus.SUCCESS
    period = SubscriptionBillingPeriod.objects.get(subscription=subscription)
    assert period.current_usage_amount == Decimal("42.35")
    assert period.usage_quantity == Decimal("128.5000")
    assert period.usage_unit == "GB"
    assert period.current_usage_updated_at is not None
    integration.refresh_from_db()
    assert integration.last_sync_status == SyncStatus.SUCCESS
    assert SubscriptionInvoice.objects.count() == 0
    assert Expense.objects.count() == 0


@pytest.mark.django_db
def test_vendor_sync_rejects_currency_mismatch_and_preserves_billing_data(monkeypatch):
    _, owner, organization, entity, _ = signed_in_owner("currency-sync@example.com")
    vendor, subscription = payg_subscription(entity)
    integration = VendorIntegration.objects.create(
        organization=organization,
        legal_entity=entity,
        vendor=vendor,
        subscription=subscription,
        name="Currency Guard",
        endpoint_url="https://api.vendor.example/usage",
        cost_json_path="cost",
        currency_json_path="currency",
    )
    monkeypatch.setattr(
        "apps.automation.services.fetch_vendor_payload",
        lambda config: ({"cost": "10.00", "currency": "EUR"}, 200),
    )

    run = sync_vendor_integration(integration, actor=owner)

    assert run.status == RunStatus.FAILED
    assert "subscription currency is USD" in run.error
    assert SubscriptionBillingPeriod.objects.count() == 0
    integration.refresh_from_db()
    assert integration.last_sync_status == SyncStatus.FAILED


@pytest.mark.django_db
def test_automation_policy_creates_only_missing_payg_periods():
    _, owner, organization, entity, _ = signed_in_owner("policy-run@example.com")
    _, subscription = payg_subscription(entity)
    policies = ensure_default_automation_policies(organization, actor=owner)
    policy = next(item for item in policies if item.kind == AutomationKind.ENSURE_PAYG_PERIODS)

    first = run_automation_policy(policy, actor=owner)
    second = run_automation_policy(policy, actor=owner)

    assert first.status == RunStatus.SUCCESS
    assert first.summary["created"] == 1
    assert second.status == RunStatus.SUCCESS
    assert second.summary["created"] == 0
    assert second.summary["already_present"] == 1
    assert SubscriptionBillingPeriod.objects.filter(subscription=subscription).count() == 1


@pytest.mark.django_db
def test_vendor_integration_api_never_returns_secret(monkeypatch):
    client, _, _, entity, _ = signed_in_owner("secret-api@example.com")
    vendor, subscription = payg_subscription(entity)

    created = client.post(
        "/api/v1/automation/vendor-integrations/",
        data={
            "name": "Secure API",
            "vendor": str(vendor.id),
            "subscription": str(subscription.id),
            "connector_type": "GENERIC_JSON",
            "enabled": True,
            "endpoint_url": "https://api.vendor.example/usage",
            "auth_type": "BEARER",
            "secret": "super-secret-token",
            "api_key_header": "X-API-Key",
            "custom_headers": {},
            "cost_json_path": "cost",
            "usage_quantity_json_path": "",
            "currency_json_path": "",
            "usage_unit_json_path": "",
            "timeout_seconds": 15,
            "auto_create_period": True,
        },
        content_type="application/json",
    )
    assert created.status_code == 201, created.content
    payload = created.json()
    assert payload["secret_configured"] is True
    assert "secret" not in payload
    assert "secret_encrypted" not in payload
    assert "super-secret-token" not in str(payload)

    listed = client.get("/api/v1/automation/vendor-integrations/")
    assert listed.status_code == 200
    assert "super-secret-token" not in listed.content.decode()


@pytest.mark.django_db
def test_saved_secret_cannot_be_reused_against_changed_endpoint():
    client, _, _, entity, _ = signed_in_owner("secret-reuse@example.com")
    vendor, subscription = payg_subscription(entity)
    created = client.post(
        "/api/v1/automation/vendor-integrations/",
        data={
            "name": "Protected Secret",
            "vendor": str(vendor.id),
            "subscription": str(subscription.id),
            "connector_type": "GENERIC_JSON",
            "enabled": True,
            "endpoint_url": "https://api.vendor.example/usage",
            "auth_type": "BEARER",
            "secret": "protected-token",
            "api_key_header": "X-API-Key",
            "custom_headers": {},
            "cost_json_path": "cost",
            "timeout_seconds": 15,
            "auto_create_period": True,
        },
        content_type="application/json",
    )
    assert created.status_code == 201, created.content

    blocked = client.post(
        "/api/v1/automation/vendor-integrations/test/",
        data={
            "integration_id": created.json()["id"],
            "subscription": str(subscription.id),
            "endpoint_url": "https://attacker.example/collect",
            "auth_type": "BEARER",
            "secret": "",
            "api_key_header": "X-API-Key",
            "custom_headers": {},
            "cost_json_path": "cost",
            "timeout_seconds": 15,
        },
        content_type="application/json",
    )
    assert blocked.status_code == 400
    assert "re-enter the secret" in str(blocked.json()).lower()


@pytest.mark.django_db
def test_private_vendor_endpoint_is_blocked_before_http_request(monkeypatch):
    monkeypatch.setattr(
        "apps.automation.services.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (2, 1, 6, "", ("127.0.0.1", 443)),
        ],
    )

    with pytest.raises(VendorIntegrationError, match="non-public"):
        fetch_vendor_payload(
            {
                "endpoint_url": "https://vendor.example/usage",
                "auth_type": "NONE",
                "custom_headers": {},
                "timeout_seconds": 5,
            }
        )


@pytest.mark.django_db
def test_disabled_entity_override_suppresses_organization_default():
    _, owner, organization, entity, _ = signed_in_owner("override-disable@example.com")
    _, subscription = payg_subscription(entity)
    default = next(
        policy
        for policy in ensure_default_automation_policies(organization, actor=owner)
        if policy.kind == AutomationKind.ENSURE_PAYG_PERIODS
    )
    AutomationPolicy.objects.create(
        organization=organization,
        legal_entity=entity,
        name="Disable entity period automation",
        kind=AutomationKind.ENSURE_PAYG_PERIODS,
        enabled=False,
        created_by=owner,
        updated_by=owner,
    )

    run = run_automation_policy(default, actor=owner)

    assert run.status == RunStatus.SUCCESS
    assert run.summary["created"] == 0
    assert SubscriptionBillingPeriod.objects.filter(subscription=subscription).count() == 0


@pytest.mark.django_db
def test_entity_override_policy_is_unique_per_kind():
    _, owner, organization, entity, _ = signed_in_owner("override@example.com")
    AutomationPolicy.objects.create(
        organization=organization,
        legal_entity=entity,
        name="Entity Sync",
        kind=AutomationKind.SYNC_VENDOR_USAGE,
        created_by=owner,
        updated_by=owner,
    )
    with pytest.raises(ValidationError):
        AutomationPolicy.objects.create(
            organization=organization,
            legal_entity=entity,
            name="Duplicate Entity Sync",
            kind=AutomationKind.SYNC_VENDOR_USAGE,
            created_by=owner,
            updated_by=owner,
        )


@pytest.mark.django_db
def test_disabled_entity_override_suppresses_organization_default_vendor_sync(monkeypatch):
    _, owner, organization, entity, _ = signed_in_owner("override-sync-disable@example.com")
    vendor, subscription = payg_subscription(entity)
    VendorIntegration.objects.create(
        organization=organization,
        legal_entity=entity,
        vendor=vendor,
        subscription=subscription,
        name="Suppressed entity sync",
        endpoint_url="https://api.vendor.example/usage",
        cost_json_path="cost",
    )
    default = next(
        policy
        for policy in ensure_default_automation_policies(organization, actor=owner)
        if policy.kind == AutomationKind.SYNC_VENDOR_USAGE
    )
    AutomationPolicy.objects.create(
        organization=organization,
        legal_entity=entity,
        name="Disable entity vendor sync",
        kind=AutomationKind.SYNC_VENDOR_USAGE,
        enabled=False,
        created_by=owner,
        updated_by=owner,
    )

    def fail_vendor_sync(*args, **kwargs):
        pytest.fail("Organization default must not sync an overridden entity.")

    monkeypatch.setattr(
        "apps.automation.services.sync_vendor_integration",
        fail_vendor_sync,
    )

    run = run_automation_policy(default, actor=owner)

    assert run.status == RunStatus.SUCCESS
    assert run.summary == {"integrations": 0, "success": 0, "failed": 0}


@pytest.mark.django_db
def test_disabled_entity_override_suppresses_organization_default_alert_refresh(monkeypatch):
    _, owner, organization, entity, _ = signed_in_owner("override-alert-disable@example.com")
    default = next(
        policy
        for policy in ensure_default_automation_policies(organization, actor=owner)
        if policy.kind == AutomationKind.REFRESH_ALERTS
    )
    AutomationPolicy.objects.create(
        organization=organization,
        legal_entity=entity,
        name="Disable entity alert refresh",
        kind=AutomationKind.REFRESH_ALERTS,
        enabled=False,
        created_by=owner,
        updated_by=owner,
    )

    def fail_alert_refresh(*args, **kwargs):
        pytest.fail("Organization default must not refresh an overridden entity.")

    monkeypatch.setattr(
        "apps.automation.services.run_alert_rules",
        fail_alert_refresh,
    )

    run = run_automation_policy(default, actor=owner)

    assert run.status == RunStatus.SUCCESS
    assert run.summary == {
        "rules_evaluated": 0,
        "active_events": 0,
        "deliveries_sent": 0,
        "deliveries_failed": 0,
    }
