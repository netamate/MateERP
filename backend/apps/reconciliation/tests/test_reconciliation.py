from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounting.models import Account, AccountType, FiscalPeriod, NormalBalance
from apps.accounting.services import create_journal, post_journal
from apps.finance.models import FinancialAccount, FinancialAccountType
from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.reconciliation.models import ReconciliationStatus
from apps.reconciliation.services import (
    complete_reconciliation,
    create_reconciliation,
    replace_reconciliation_items,
)


@pytest.mark.django_db
def test_reconciliation_requires_zero_difference_and_becomes_immutable():
    owner = User.objects.create_user(email="recon-owner@example.com", password="test-pass-123")
    _, entity, membership = create_organization_with_owner(
        owner=owner,
        name="Reconciliation Test",
        base_currency="USD",
    )
    FiscalPeriod.objects.create(
        legal_entity=entity,
        name="FY 2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    cash = Account.objects.create(
        legal_entity=entity,
        code="1000",
        name="Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
    )
    equity = Account.objects.create(
        legal_entity=entity,
        code="3000",
        name="Opening Equity",
        account_type=AccountType.EQUITY,
        normal_balance=NormalBalance.CREDIT,
    )
    financial_account = FinancialAccount.objects.create(
        legal_entity=entity,
        name="Operating Bank",
        account_type=FinancialAccountType.BANK,
        currency="USD",
        ledger_account=cash,
    )
    journal = create_journal(
        membership=membership,
        legal_entity=entity,
        entry_date=date(2026, 9, 1),
        memo="Opening bank funding",
        lines=[
            {
                "account_id": cash.id,
                "description": "Bank funding",
                "debit": Decimal("100.00"),
                "credit": Decimal("0"),
                "currency": "USD",
                "fx_rate": Decimal("1"),
            },
            {
                "account_id": equity.id,
                "description": "Opening equity",
                "debit": Decimal("0"),
                "credit": Decimal("100.00"),
                "currency": "USD",
                "fx_rate": Decimal("1"),
            },
        ],
    )
    post_journal(membership=membership, journal=journal)
    bank_line = journal.lines.get(account=cash)

    reconciliation = create_reconciliation(
        membership=membership,
        legal_entity=entity,
        financial_account=financial_account,
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30),
        statement_ending_balance=Decimal("100.00"),
    )
    with pytest.raises(ValidationError, match="difference must be zero"):
        complete_reconciliation(membership=membership, reconciliation=reconciliation)

    replace_reconciliation_items(
        membership=membership,
        reconciliation=reconciliation,
        journal_line_ids=[bank_line.id],
    )
    completed = complete_reconciliation(
        membership=membership,
        reconciliation=reconciliation,
    )
    assert completed.status == ReconciliationStatus.COMPLETED

    with pytest.raises(ValidationError, match="immutable"):
        replace_reconciliation_items(
            membership=membership,
            reconciliation=completed,
            journal_line_ids=[],
        )
