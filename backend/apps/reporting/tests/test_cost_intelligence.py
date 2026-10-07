from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from apps.automation.models import AutomationKind, AutomationPolicy, VendorIntegration
from apps.finance.models import Vendor
from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.operations.models import (
    BillingMode,
    BillingPayment,
    BillingPaymentAllocation,
    Subscription,
    SubscriptionBillingPeriod,
    SubscriptionInvoice,
)
from apps.reporting.selectors import operations_cost_intelligence


def setup_reporting(email="cost-report@example.com"):
    owner = User.objects.create_user(email=email, password="test-pass-123")
    organization, entity, _ = create_organization_with_owner(
        owner=owner,
        name="Cost Intelligence",
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
def test_cost_intelligence_keeps_currencies_separate_and_surfaces_health():
    client, owner, organization, entity = setup_reporting()
    vendor = Vendor.objects.create(legal_entity=entity, code="CLOUD", name="Cloud Vendor")
    usd = Subscription.objects.create(
        legal_entity=entity,
        vendor=vendor,
        name="USD PAYG",
        billing_mode=BillingMode.PAYG,
        estimated_cost=Decimal("20.00"),
        monthly_budget=Decimal("25.00"),
        amount=Decimal("0"),
        currency="USD",
    )
    eur = Subscription.objects.create(
        legal_entity=entity,
        vendor=vendor,
        name="EUR PAYG",
        billing_mode=BillingMode.PAYG,
        estimated_cost=Decimal("8.00"),
        monthly_budget=Decimal("20.00"),
        amount=Decimal("0"),
        currency="EUR",
    )
    usd_period = SubscriptionBillingPeriod.objects.create(
        legal_entity=entity,
        subscription=usd,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        estimated_cost=Decimal("20.00"),
        current_usage_amount=Decimal("30.00"),
        created_by=owner,
    )
    SubscriptionBillingPeriod.objects.create(
        legal_entity=entity,
        subscription=eur,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        estimated_cost=Decimal("8.00"),
        current_usage_amount=Decimal("9.00"),
        created_by=owner,
    )
    invoice = SubscriptionInvoice.objects.create(
        legal_entity=entity,
        billing_period=usd_period,
        vendor=vendor,
        invoice_number="INV-COST-1",
        invoice_date=date(2026, 9, 30),
        currency="USD",
        subtotal=Decimal("28.00"),
        tax_amount=Decimal("0"),
        total_amount=Decimal("28.00"),
        created_by=owner,
    )
    payment = BillingPayment.objects.create(
        legal_entity=entity,
        subscription=usd,
        paid_on=date(2026, 9, 30),
        amount=Decimal("20.00"),
        currency="USD",
        created_by=owner,
    )
    BillingPaymentAllocation.objects.create(
        payment=payment,
        invoice=invoice,
        amount=Decimal("20.00"),
    )
    VendorIntegration.objects.create(
        organization=organization,
        legal_entity=entity,
        vendor=vendor,
        subscription=usd,
        name="USD Vendor API",
        endpoint_url="https://api.vendor.example/usage",
        cost_json_path="cost",
        created_by=owner,
        updated_by=owner,
    )
    AutomationPolicy.objects.create(
        organization=organization,
        name="Ensure PAYG",
        kind=AutomationKind.ENSURE_PAYG_PERIODS,
        enabled=True,
        created_by=owner,
        updated_by=owner,
    )

    data = operations_cost_intelligence(
        entity,
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30),
    )

    by_currency = {row["currency"]: row for row in data["currency_totals"]}
    assert set(by_currency) == {"USD", "EUR"}
    assert by_currency["USD"]["actual_billed"] == "28.00"
    assert by_currency["USD"]["paid"] == "20.00"
    assert by_currency["USD"]["outstanding"] == "8.00"
    assert by_currency["EUR"]["current_usage"] == "9.00"

    usd_row = next(
        row for row in data["subscriptions"] if row["subscription_id"] == str(usd.id)
    )
    assert usd_row["forecast"] == "30.00"
    assert usd_row["over_budget_forecast"] is True
    assert usd_row["forecast_variance"] == "5.00"

    assert data["reconciliation_health"]["invoice_unmatched"] == 1
    assert data["reconciliation_health"]["payment_unmatched"] == 1
    assert data["integration_health"]["active"] == 1
    assert data["integration_health"]["never_synced"] == 1
    assert data["automation_health"]["enabled_policies"] == 1

    response = client.get(
        "/api/v1/reporting/cost-intelligence/",
        {"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    assert response.status_code == 200
    assert len(response.json()["currency_totals"]) == 2

    csv_response = client.get(
        "/api/v1/reporting/cost-intelligence/export/",
        {
            "section": "subscriptions",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
        },
    )
    assert csv_response.status_code == 200
    assert csv_response["Content-Type"] == "text/csv"
    assert "USD PAYG" in csv_response.content.decode()
