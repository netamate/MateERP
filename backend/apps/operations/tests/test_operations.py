from datetime import date
from decimal import Decimal

import pytest

from apps.accounting.models import Account, AccountType, NormalBalance
from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.operations.models import Domain, InfrastructureAsset, Subscription
from apps.operations.selectors import renewal_calendar
from apps.operations.services import renew_domain
from apps.planning.models import CostCenter, Product


@pytest.fixture
def operations_context(db):
    owner = User.objects.create_user(email="operations-owner@example.com", password="test-pass-123")
    _, entity, membership = create_organization_with_owner(
        owner=owner,
        name="Operations Test",
        base_currency="USD",
    )
    expense_account = Account.objects.create(
        legal_entity=entity,
        code="5100",
        name="Domain and Infrastructure Expense",
        account_type=AccountType.EXPENSE,
        normal_balance=NormalBalance.DEBIT,
    )
    payable = Account.objects.create(
        legal_entity=entity,
        code="2100",
        name="Accounts Payable",
        account_type=AccountType.LIABILITY,
        normal_balance=NormalBalance.CREDIT,
    )
    product = Product.objects.create(legal_entity=entity, code="MATEDESK", name="MateDesk")
    cost_center = CostCenter.objects.create(
        legal_entity=entity,
        code="INFRA",
        name="Infrastructure",
    )
    return {
        "owner": owner,
        "entity": entity,
        "membership": membership,
        "expense_account": expense_account,
        "payable": payable,
        "product": product,
        "cost_center": cost_center,
    }


@pytest.mark.django_db
def test_domain_renewal_preserves_history_and_can_generate_expense(operations_context):
    context = operations_context
    domain = Domain.objects.create(
        legal_entity=context["entity"],
        domain_name="matedesk.pro",
        registrar="Namecheap",
        expiry_date=date(2026, 10, 3),
        renewal_amount=Decimal("14.98"),
        currency="USD",
        product=context["product"],
        expense_account=context["expense_account"],
        payable_account=context["payable"],
    )

    renewal = renew_domain(
        membership=context["membership"],
        domain=domain,
        renewed_on=date(2026, 9, 20),
        new_expiry_date=date(2027, 10, 3),
        amount=Decimal("14.98"),
        currency="USD",
        fx_rate=Decimal("1"),
        generate_expense=True,
    )
    domain.refresh_from_db()

    assert renewal.previous_expiry_date == date(2026, 10, 3)
    assert renewal.new_expiry_date == date(2027, 10, 3)
    assert renewal.expense is not None
    assert renewal.expense.amount == Decimal("14.98")
    assert domain.expiry_date == date(2027, 10, 3)
    assert domain.renewal_history.count() == 1


@pytest.mark.django_db
def test_renewal_calendar_aggregates_without_duplicate_renewal_records(operations_context):
    context = operations_context
    Subscription.objects.create(
        legal_entity=context["entity"],
        name="GitHub Team",
        amount=Decimal("16.00"),
        currency="USD",
        next_renewal_date=date(2026, 9, 24),
        product=context["product"],
        cost_center=context["cost_center"],
    )
    Domain.objects.create(
        legal_entity=context["entity"],
        domain_name="mateassist.site",
        expiry_date=date(2026, 10, 3),
        renewal_amount=Decimal("12.00"),
        currency="USD",
        product=context["product"],
    )
    InfrastructureAsset.objects.create(
        legal_entity=context["entity"],
        name="MateServer",
        asset_type="VPS",
        next_renewal_date=date(2026, 9, 21),
        renewal_amount=Decimal("48.50"),
        currency="USD",
        product=context["product"],
        cost_center=context["cost_center"],
    )

    rows = renewal_calendar(
        context["entity"],
        start_date=date(2026, 9, 18),
        end_date=date(2026, 10, 10),
    )

    assert [row["source_type"] for row in rows] == [
        "INFRASTRUCTURE",
        "SUBSCRIPTION",
        "DOMAIN",
    ]
    assert {row["name"] for row in rows} == {"MateServer", "GitHub Team", "mateassist.site"}
