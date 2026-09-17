from datetime import date
from decimal import Decimal

import pytest

from apps.accounting.models import Account, AccountType, FiscalPeriod, NormalBalance
from apps.finance.models import Vendor
from apps.finance.services import (
    approve_expense,
    create_expense,
    record_income,
    submit_expense,
)
from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.planning.models import CostCenter, Product
from apps.planning.services import replace_expense_allocations
from apps.reporting.selectors import (
    cost_center_spend,
    expense_report,
    product_cost,
    revenue_report,
    vendor_spend,
)


@pytest.mark.django_db
def test_enterprise_reports_derive_from_posted_finance_and_allocations():
    owner = User.objects.create_user(email="report-owner@example.com", password="test-pass-123")
    _, entity, membership = create_organization_with_owner(
        owner=owner,
        name="Reporting Test",
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
    cash = Account.objects.create(
        legal_entity=entity,
        code="1000",
        name="Cash",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
    )
    revenue = Account.objects.create(
        legal_entity=entity,
        code="4000",
        name="Service Revenue",
        account_type=AccountType.REVENUE,
        normal_balance=NormalBalance.CREDIT,
    )
    from apps.finance.models import FinancialAccount, FinancialAccountType

    financial_account = FinancialAccount.objects.create(
        legal_entity=entity,
        name="Operating Cash",
        account_type=FinancialAccountType.CASH,
        currency="USD",
        ledger_account=cash,
    )
    vendor = Vendor.objects.create(legal_entity=entity, code="VPS", name="Hosting Vendor")
    cost_center = CostCenter.objects.create(legal_entity=entity, code="INFRA", name="Infrastructure")
    product = Product.objects.create(legal_entity=entity, code="MATEDESK", name="MateDesk")

    expense = create_expense(
        membership=membership,
        legal_entity=entity,
        vendor=vendor,
        expense_date=date(2026, 9, 1),
        description="Shared VPS",
        amount=Decimal("120.00"),
        tax_amount=Decimal("0"),
        currency="USD",
        fx_rate=Decimal("1"),
        expense_account=expense_account,
        payable_account=payable,
    )
    replace_expense_allocations(
        membership=membership,
        expense=expense,
        allocations=[
            {
                "cost_center": cost_center,
                "product": product,
                "project": None,
                "amount": Decimal("75.00"),
                "note": "Shared production infrastructure",
            }
        ],
    )
    submit_expense(membership=membership, expense=expense)
    approve_expense(membership=membership, expense=expense)
    record_income(
        membership=membership,
        legal_entity=entity,
        income_date=date(2026, 9, 2),
        payer_name="Client A",
        description="Managed services",
        amount=Decimal("300.00"),
        currency="USD",
        fx_rate=Decimal("1"),
        revenue_account=revenue,
        financial_account=financial_account,
    )

    assert expense_report(entity)["total"] == Decimal("120.00")
    assert revenue_report(entity)["total"] == Decimal("300.00")
    assert vendor_spend(entity)["rows"][0]["base_amount"] == Decimal("120.00")
    assert product_cost(entity)["rows"][0]["base_amount"] == Decimal("75.00")
    assert cost_center_spend(entity)["rows"][0]["base_amount"] == Decimal("75.00")
