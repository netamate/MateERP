from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied

from apps.accounting.models import Account, AccountType, FiscalPeriod, NormalBalance
from apps.finance.models import (
    ExpenseStatus,
    FinancialAccount,
    FinancialAccountType,
    FounderFundingType,
    ReimbursementStatus,
)
from apps.finance.services import (
    approve_expense,
    approve_reimbursement,
    create_expense,
    create_reimbursement,
    pay_expense,
    pay_reimbursement,
    record_founder_funding,
    record_income,
    record_transfer,
    submit_expense,
    submit_reimbursement,
)
from apps.identity.models import Membership, Role, User
from apps.identity.services import create_organization_with_owner


@pytest.fixture
def finance_context(db):
    owner = User.objects.create_user(email="owner@example.com", password="test-pass-123")
    _, entity, membership = create_organization_with_owner(
        owner=owner,
        name="NetaMate Test",
        base_currency="USD",
    )
    FiscalPeriod.objects.create(
        legal_entity=entity,
        name="FY 2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )

    def account(code, name, account_type, normal_balance):
        return Account.objects.create(
            legal_entity=entity,
            code=code,
            name=name,
            account_type=account_type,
            normal_balance=normal_balance,
        )

    cash = account("1000", "Cash", AccountType.ASSET, NormalBalance.DEBIT)
    bank = account("1010", "Bank", AccountType.ASSET, NormalBalance.DEBIT)
    expense_account = account("5000", "Operations", AccountType.EXPENSE, NormalBalance.DEBIT)
    payable = account("2000", "Accounts Payable", AccountType.LIABILITY, NormalBalance.CREDIT)
    reimbursement_payable = account(
        "2010",
        "Reimbursements Payable",
        AccountType.LIABILITY,
        NormalBalance.CREDIT,
    )
    revenue = account("4000", "Service Revenue", AccountType.REVENUE, NormalBalance.CREDIT)
    equity = account("3000", "Founder Capital", AccountType.EQUITY, NormalBalance.CREDIT)

    cash_finance = FinancialAccount.objects.create(
        legal_entity=entity,
        name="Operating Cash",
        account_type=FinancialAccountType.CASH,
        currency="USD",
        ledger_account=cash,
    )
    bank_finance = FinancialAccount.objects.create(
        legal_entity=entity,
        name="Operating Bank",
        account_type=FinancialAccountType.BANK,
        currency="USD",
        ledger_account=bank,
    )
    return {
        "owner": owner,
        "entity": entity,
        "membership": membership,
        "cash_finance": cash_finance,
        "bank_finance": bank_finance,
        "expense_account": expense_account,
        "payable": payable,
        "reimbursement_payable": reimbursement_payable,
        "revenue": revenue,
        "equity": equity,
    }


@pytest.mark.django_db
def test_expense_approval_and_payment_create_balanced_journals(finance_context):
    context = finance_context
    expense = create_expense(
        membership=context["membership"],
        legal_entity=context["entity"],
        expense_date=date(2026, 9, 1),
        description="VPS hosting",
        amount=Decimal("120.00"),
        tax_amount=Decimal("0"),
        currency="USD",
        fx_rate=Decimal("1"),
        expense_account=context["expense_account"],
        payable_account=context["payable"],
    )
    submit_expense(membership=context["membership"], expense=expense)
    approve_expense(membership=context["membership"], expense=expense)
    expense.refresh_from_db()
    assert expense.status == ExpenseStatus.APPROVED
    assert expense.journal_entry.lines.count() == 2

    pay_expense(
        membership=context["membership"],
        expense=expense,
        financial_account=context["cash_finance"],
        payment_date=date(2026, 9, 2),
        amount=Decimal("120.00"),
        currency="USD",
        fx_rate=Decimal("1"),
    )
    expense.refresh_from_db()
    assert expense.status == ExpenseStatus.PAID
    assert expense.payments.count() == 1
    assert expense.payments.first().journal_entry.lines.count() == 2


@pytest.mark.django_db
def test_income_transfer_and_founder_contribution_post_to_ledger(finance_context):
    context = finance_context
    income = record_income(
        membership=context["membership"],
        legal_entity=context["entity"],
        income_date=date(2026, 9, 3),
        payer_name="Client A",
        description="Managed IT services",
        amount=Decimal("500.00"),
        currency="USD",
        fx_rate=Decimal("1"),
        revenue_account=context["revenue"],
        financial_account=context["cash_finance"],
    )
    assert income.journal_entry.lines.count() == 2

    transfer = record_transfer(
        membership=context["membership"],
        legal_entity=context["entity"],
        transfer_date=date(2026, 9, 4),
        from_account=context["cash_finance"],
        to_account=context["bank_finance"],
        source_amount=Decimal("100.00"),
        destination_amount=Decimal("100.00"),
        source_fx_rate=Decimal("1"),
        destination_fx_rate=Decimal("1"),
    )
    assert transfer.journal_entry.lines.count() == 2

    funding = record_founder_funding(
        membership=context["membership"],
        legal_entity=context["entity"],
        funding_date=date(2026, 9, 5),
        founder_name="Founder",
        funding_type=FounderFundingType.CONTRIBUTION,
        amount=Decimal("1000.00"),
        currency="USD",
        fx_rate=Decimal("1"),
        financial_account=context["bank_finance"],
        counter_account=context["equity"],
    )
    assert funding.journal_entry.lines.count() == 2


@pytest.mark.django_db
def test_reimbursement_workflow_posts_accrual_and_payment(finance_context):
    context = finance_context
    reimbursement = create_reimbursement(
        membership=context["membership"],
        legal_entity=context["entity"],
        claimant=context["owner"],
        expense_date=date(2026, 9, 6),
        description="Founder paid domain renewal",
        amount=Decimal("25.00"),
        currency="USD",
        fx_rate=Decimal("1"),
        expense_account=context["expense_account"],
        payable_account=context["reimbursement_payable"],
    )
    submit_reimbursement(membership=context["membership"], reimbursement=reimbursement)
    approve_reimbursement(membership=context["membership"], reimbursement=reimbursement)
    reimbursement.refresh_from_db()
    assert reimbursement.status == ReimbursementStatus.APPROVED

    pay_reimbursement(
        membership=context["membership"],
        reimbursement=reimbursement,
        financial_account=context["cash_finance"],
        payment_date=date(2026, 9, 7),
        amount=Decimal("25.00"),
        currency="USD",
        fx_rate=Decimal("1"),
    )
    reimbursement.refresh_from_db()
    assert reimbursement.status == ReimbursementStatus.PAID


@pytest.mark.django_db
def test_member_cannot_approve_expense(finance_context):
    context = finance_context
    member_user = User.objects.create_user(email="member@example.com", password="test-pass-123")
    member = Membership.objects.create(
        organization=context["membership"].organization,
        user=member_user,
        role=Role.MEMBER,
        all_legal_entities=True,
    )
    expense = create_expense(
        membership=member,
        legal_entity=context["entity"],
        expense_date=date(2026, 9, 8),
        description="Office supplies",
        amount=Decimal("10.00"),
        tax_amount=Decimal("0"),
        currency="USD",
        fx_rate=Decimal("1"),
        expense_account=context["expense_account"],
        payable_account=context["payable"],
    )
    submit_expense(membership=member, expense=expense)
    with pytest.raises(PermissionDenied):
        approve_expense(membership=member, expense=expense)
