from datetime import date
from decimal import Decimal

import pytest

from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.operations.models import (
    BillingCycle,
    ServiceType,
    Subscription,
    SubscriptionPayment,
)
from apps.operations.selectors import renewal_calendar
from apps.operations.services import record_subscription_payment


@pytest.fixture
def operations_context(db):
    owner = User.objects.create_user(
        email="operations-owner@example.com",
        password="test-pass-123",
    )
    _, entity, membership = create_organization_with_owner(
        owner=owner,
        name="Operations Test",
        base_currency="USD",
    )
    return {
        "owner": owner,
        "entity": entity,
        "membership": membership,
    }


@pytest.mark.django_db
def test_renewal_calendar_uses_unified_subscription_source(operations_context):
    context = operations_context
    Subscription.objects.create(
        legal_entity=context["entity"],
        name="GitHub Team",
        service_type=ServiceType.SAAS,
        amount=Decimal("16.00"),
        currency="USD",
        next_renewal_date=date(2026, 9, 24),
        payment_method="Business card",
        reference="github-team",
    )

    rows = renewal_calendar(
        context["entity"],
        start_date=date(2026, 9, 18),
        end_date=date(2026, 10, 10),
    )

    assert len(rows) == 1
    assert rows[0]["source_type"] == "SUBSCRIPTION"
    assert rows[0]["service_type"] == ServiceType.SAAS
    assert rows[0]["name"] == "GitHub Team"
    assert rows[0]["payment_method"] == "Business card"
    assert rows[0]["reference"] == "github-team"


@pytest.mark.django_db
def test_mark_paid_records_history_and_advances_monthly_due_date(operations_context):
    context = operations_context
    subscription = Subscription.objects.create(
        legal_entity=context["entity"],
        name="ChatGPT Plus",
        service_type=ServiceType.AI,
        amount=Decimal("20.00"),
        currency="USD",
        billing_cycle=BillingCycle.MONTHLY,
        next_renewal_date=date(2026, 10, 31),
    )

    payment = record_subscription_payment(
        membership=context["membership"],
        subscription=subscription,
        paid_on=date(2026, 10, 31),
        reference="October renewal",
    )
    subscription.refresh_from_db()

    assert payment.previous_due_date == date(2026, 10, 31)
    assert payment.next_due_date == date(2026, 11, 30)
    assert payment.amount == Decimal("20.00")
    assert payment.created_by == context["owner"]
    assert subscription.next_renewal_date == date(2026, 11, 30)
    assert SubscriptionPayment.objects.filter(subscription=subscription).count() == 1


@pytest.mark.django_db
def test_mark_paid_advances_custom_cycle(operations_context):
    context = operations_context
    subscription = Subscription.objects.create(
        legal_entity=context["entity"],
        name="Custom Service",
        amount=Decimal("12.00"),
        currency="USD",
        billing_cycle=BillingCycle.CUSTOM,
        custom_cycle_days=45,
        next_renewal_date=date(2026, 10, 7),
    )

    payment = record_subscription_payment(
        membership=context["membership"],
        subscription=subscription,
        paid_on=date(2026, 10, 7),
    )

    assert payment.next_due_date == date(2026, 11, 21)
