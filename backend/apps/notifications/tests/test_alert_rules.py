from datetime import timedelta
from decimal import Decimal

import pytest
from apps.finance.models import Vendor
from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.operations.models import (
    BillingMode,
    Subscription,
    SubscriptionBillingPeriod,
    SubscriptionInvoice,
)
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from apps.notifications.models import (
    AlertFrequency,
    AlertRule,
    DeliveryChannel,
    Notification,
    NotificationDelivery,
    NotificationKind,
)
from apps.notifications.services import alert_rule_is_due, ensure_default_alert_rules


def signed_in_owner(email="alerts-owner@example.com"):
    owner = User.objects.create_user(email=email, password="test-pass-123")
    organization, entity, _ = create_organization_with_owner(
        owner=owner,
        name=f"Alerts {email}",
        base_currency="USD",
    )
    client = Client()
    client.force_login(owner)
    session = client.session
    session["active_organization_id"] = str(organization.id)
    session["active_legal_entity_id"] = str(entity.id)
    session.save()
    return client, owner, organization, entity


@pytest.mark.django_db
def test_default_alert_rules_are_seeded_and_exposed():
    client, _, organization, _ = signed_in_owner()

    response = client.get("/api/v1/notifications/rules/")

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 5
    assert {row["signal"] for row in rows} == {
        NotificationKind.RENEWAL_DUE,
        NotificationKind.BUDGET_THRESHOLD,
        NotificationKind.MISSING_INVOICE,
        NotificationKind.INVOICE_OVERDUE,
        NotificationKind.RECONCILIATION_NEEDED,
    }
    assert AlertRule.objects.filter(organization=organization).count() == 5


@pytest.mark.django_db
def test_budget_threshold_alerts_are_idempotent_and_resolve_when_condition_clears():
    client, _, organization, entity = signed_in_owner("budget-alert@example.com")
    subscription = Subscription.objects.create(
        legal_entity=entity,
        name="Azure PAYG",
        billing_mode=BillingMode.PAYG,
        amount=Decimal("0"),
        estimated_cost=Decimal("60"),
        monthly_budget=Decimal("100"),
        budget_alert_thresholds=[50, 80, 100],
        currency="USD",
    )
    today = timezone.localdate()
    period = SubscriptionBillingPeriod.objects.create(
        legal_entity=entity,
        subscription=subscription,
        period_start=today.replace(day=1),
        period_end=today + timedelta(days=10),
        estimated_cost=Decimal("60"),
        current_usage_amount=Decimal("85"),
    )

    first = client.post(
        "/api/v1/notifications/rules/run-now/",
        data={},
        content_type="application/json",
    )
    assert first.status_code == 200, first.content

    alerts = Notification.objects.filter(
        organization=organization,
        kind=NotificationKind.BUDGET_THRESHOLD,
        resolved_at__isnull=True,
    )
    assert alerts.count() == 2
    assert any("80%" in row.title for row in alerts)
    assert (
        NotificationDelivery.objects.filter(
            signal=NotificationKind.BUDGET_THRESHOLD,
            channel=DeliveryChannel.IN_APP,
        ).count()
        == 2
    )

    second = client.post(
        "/api/v1/notifications/rules/run-now/",
        data={},
        content_type="application/json",
    )
    assert second.status_code == 200
    assert (
        Notification.objects.filter(
            organization=organization,
            kind=NotificationKind.BUDGET_THRESHOLD,
        ).count()
        == 2
    )
    assert (
        NotificationDelivery.objects.filter(signal=NotificationKind.BUDGET_THRESHOLD).count() == 2
    )

    period.current_usage_amount = Decimal("40")
    period.save()
    third = client.post(
        "/api/v1/notifications/rules/run-now/",
        data={},
        content_type="application/json",
    )
    assert third.status_code == 200
    assert (
        Notification.objects.filter(
            organization=organization,
            kind=NotificationKind.BUDGET_THRESHOLD,
            resolved_at__isnull=True,
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_missing_invoice_alert_auto_resolves_after_invoice_is_recorded():
    client, _, organization, entity = signed_in_owner("invoice-alert@example.com")
    vendor = Vendor.objects.create(
        legal_entity=entity,
        code="CLOUD",
        name="Cloud Vendor",
    )
    subscription = Subscription.objects.create(
        legal_entity=entity,
        vendor=vendor,
        name="Cloud Service",
        amount=Decimal("10"),
        currency="USD",
    )
    today = timezone.localdate()
    period = SubscriptionBillingPeriod.objects.create(
        legal_entity=entity,
        subscription=subscription,
        period_start=today - timedelta(days=40),
        period_end=today - timedelta(days=5),
        estimated_cost=Decimal("10"),
    )

    first = client.post(
        "/api/v1/notifications/rules/run-now/",
        data={},
        content_type="application/json",
    )
    assert first.status_code == 200
    alert = Notification.objects.get(
        organization=organization,
        kind=NotificationKind.MISSING_INVOICE,
    )
    assert alert.resolved_at is None

    SubscriptionInvoice.objects.create(
        legal_entity=entity,
        billing_period=period,
        vendor=vendor,
        invoice_number="INV-MISSING-1",
        invoice_date=period.period_end,
        currency="USD",
        subtotal=Decimal("10"),
        tax_amount=Decimal("0"),
        total_amount=Decimal("10"),
    )

    second = client.post(
        "/api/v1/notifications/rules/run-now/",
        data={},
        content_type="application/json",
    )
    assert second.status_code == 200
    alert.refresh_from_db()
    assert alert.resolved_at is not None


@pytest.mark.django_db
def test_overdue_and_reconciliation_signals_are_separate():
    client, _, organization, entity = signed_in_owner("reconcile-alert@example.com")
    vendor = Vendor.objects.create(
        legal_entity=entity,
        code="VENDOR-1",
        name="Vendor One",
    )
    subscription = Subscription.objects.create(
        legal_entity=entity,
        vendor=vendor,
        name="Managed Service",
        amount=Decimal("25"),
        currency="USD",
    )
    today = timezone.localdate()
    period = SubscriptionBillingPeriod.objects.create(
        legal_entity=entity,
        subscription=subscription,
        period_start=today - timedelta(days=35),
        period_end=today - timedelta(days=5),
        estimated_cost=Decimal("25"),
    )
    invoice = SubscriptionInvoice.objects.create(
        legal_entity=entity,
        billing_period=period,
        vendor=vendor,
        invoice_number="INV-OVERDUE-1",
        invoice_date=today - timedelta(days=5),
        due_date=today - timedelta(days=2),
        currency="USD",
        subtotal=Decimal("25"),
        tax_amount=Decimal("0"),
        total_amount=Decimal("25"),
    )

    response = client.post(
        "/api/v1/notifications/rules/run-now/",
        data={},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert (
        Notification.objects.filter(
            organization=organization,
            kind=NotificationKind.INVOICE_OVERDUE,
            resolved_at__isnull=True,
        ).count()
        == 1
    )
    assert (
        Notification.objects.filter(
            organization=organization,
            kind=NotificationKind.RECONCILIATION_NEEDED,
            resolved_at__isnull=True,
        ).count()
        == 1
    )
    assert "outstanding" in Notification.objects.get(kind=NotificationKind.INVOICE_OVERDUE).message
    assert invoice.expense_id is None


@pytest.mark.django_db
def test_rule_schedule_prevents_duplicate_daily_evaluation_but_force_command_runs():
    _, _, organization, _ = signed_in_owner("schedule-alert@example.com")
    rules = ensure_default_alert_rules(organization)
    rule = next(row for row in rules if row.signal == NotificationKind.MISSING_INVOICE)
    rule.frequency = AlertFrequency.DAILY
    rule.schedule_hour = 0
    rule.last_evaluated_at = timezone.now()
    rule.save()

    assert alert_rule_is_due(rule, now=timezone.now()) is False

    call_command("refresh_notifications", force=True)
    rule.refresh_from_db()
    assert rule.last_evaluated_at is not None


@pytest.mark.django_db
def test_rule_configuration_api_validates_scope_and_recipient_membership():
    client, owner, organization, entity = signed_in_owner("rule-config@example.com")
    client.get("/api/v1/notifications/rules/")
    rule = AlertRule.objects.get(
        organization=organization,
        signal=NotificationKind.BUDGET_THRESHOLD,
        legal_entity__isnull=True,
    )

    updated = client.patch(
        f"/api/v1/notifications/rules/{rule.id}/",
        data={
            "enabled": True,
            "frequency": "HOURLY",
            "schedule_timezone": "Asia/Dhaka",
            "in_app_enabled": True,
            "email_enabled": True,
            "email_recipients": ["finance@example.com"],
            "recipient_user_ids": [str(owner.id)],
        },
        content_type="application/json",
    )
    assert updated.status_code == 200, updated.content
    payload = updated.json()
    assert payload["schedule_timezone"] == "Asia/Dhaka"
    assert payload["email_recipients"] == ["finance@example.com"]
    assert payload["recipient_users"][0]["id"] == str(owner.id)

    invalid = client.patch(
        f"/api/v1/notifications/rules/{rule.id}/",
        data={"recipient_user_ids": ["00000000-0000-0000-0000-000000000001"]},
        content_type="application/json",
    )
    assert invalid.status_code == 400

    override = client.post(
        "/api/v1/notifications/rules/",
        data={
            "name": "Entity budget override",
            "signal": NotificationKind.BUDGET_THRESHOLD,
            "legal_entity": str(entity.id),
            "frequency": "HOURLY",
            "schedule_hour": 0,
            "schedule_timezone": "Asia/Dhaka",
            "in_app_enabled": True,
            "email_enabled": False,
            "hermes_enabled": False,
            "renewal_days": [30, 7, 1, 0],
            "grace_days": 0,
        },
        content_type="application/json",
    )
    assert override.status_code == 201, override.content
    assert override.json()["legal_entity"] == str(entity.id)
