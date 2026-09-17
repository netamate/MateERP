from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounting.models import Account, AccountType, FiscalPeriod, NormalBalance
from apps.finance.services import approve_expense, create_expense, submit_expense
from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.planning.models import Budget, BudgetLine, CostCenter
from apps.planning.selectors import budget_actuals
from apps.planning.services import replace_expense_allocations


@pytest.fixture
def planning_context(db):
    owner = User.objects.create_user(email="planning-owner@example.com", password="test-pass-123")
    _, entity, membership = create_organization_with_owner(
        owner=owner,
        name="Planning Test",
        base_currency="USD",
    )
    FiscalPeriod.objects.create(
        legal_entity=entity,
        name="FY 2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    expense_account = Account.objects.create(
        legal_entity=entity,
        code="5000",
        name="Infrastructure Expense",
        account_type=AccountType.EXPENSE,
        normal_balance=NormalBalance.DEBIT,
    )
    payable = Account.objects.create(
        legal_entity=entity,
        code="2000",
        name="Accounts Payable",
        account_type=AccountType.LIABILITY,
        normal_balance=NormalBalance.CREDIT,
    )
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
        "cost_center": cost_center,
    }


@pytest.mark.django_db
def test_allocations_store_authoritative_amounts_and_drive_budget_actuals(planning_context):
    context = planning_context
    expense = create_expense(
        membership=context["membership"],
        legal_entity=context["entity"],
        expense_date=date(2026, 9, 1),
        description="Shared infrastructure",
        amount=Decimal("120.00"),
        tax_amount=Decimal("0"),
        currency="USD",
        fx_rate=Decimal("1"),
        expense_account=context["expense_account"],
        payable_account=context["payable"],
    )
    replace_expense_allocations(
        membership=context["membership"],
        expense=expense,
        allocations=[
            {
                "cost_center": context["cost_center"],
                "product": None,
                "project": None,
                "amount": Decimal("70.00"),
                "note": "Allocated to infrastructure",
            }
        ],
    )
    submit_expense(membership=context["membership"], expense=expense)
    approve_expense(membership=context["membership"], expense=expense)

    budget = Budget.objects.create(
        legal_entity=context["entity"],
        name="September Infrastructure",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30),
        status="ACTIVE",
    )
    BudgetLine.objects.create(
        budget=budget,
        cost_center=context["cost_center"],
        amount=Decimal("100.00"),
    )

    report = budget_actuals(budget)
    assert report["total_budget"] == Decimal("100.00")
    assert report["total_actual"] == Decimal("70.00")
    assert report["total_variance"] == Decimal("30.00")
    assert report["lines"][0]["utilization_percent"] == Decimal("70.00")


@pytest.mark.django_db
def test_account_budget_actual_comes_from_posted_ledger(planning_context):
    context = planning_context
    expense = create_expense(
        membership=context["membership"],
        legal_entity=context["entity"],
        expense_date=date(2026, 9, 5),
        description="Server hosting",
        amount=Decimal("80.00"),
        tax_amount=Decimal("0"),
        currency="USD",
        fx_rate=Decimal("1"),
        expense_account=context["expense_account"],
        payable_account=context["payable"],
    )
    submit_expense(membership=context["membership"], expense=expense)
    approve_expense(membership=context["membership"], expense=expense)

    budget = Budget.objects.create(
        legal_entity=context["entity"],
        name="September Expense Account",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30),
    )
    BudgetLine.objects.create(
        budget=budget,
        expense_account=context["expense_account"],
        amount=Decimal("100.00"),
    )

    report = budget_actuals(budget)
    assert report["total_actual"] == Decimal("80.00")


@pytest.mark.django_db
def test_allocations_cannot_exceed_expense_amount(planning_context):
    context = planning_context
    expense = create_expense(
        membership=context["membership"],
        legal_entity=context["entity"],
        expense_date=date(2026, 9, 10),
        description="Allocation validation",
        amount=Decimal("50.00"),
        tax_amount=Decimal("0"),
        currency="USD",
        fx_rate=Decimal("1"),
        expense_account=context["expense_account"],
        payable_account=context["payable"],
    )

    with pytest.raises(ValidationError, match="cannot exceed"):
        replace_expense_allocations(
            membership=context["membership"],
            expense=expense,
            allocations=[
                {
                    "cost_center": context["cost_center"],
                    "product": None,
                    "project": None,
                    "amount": Decimal("60.00"),
                    "note": "Too much",
                }
            ],
        )
