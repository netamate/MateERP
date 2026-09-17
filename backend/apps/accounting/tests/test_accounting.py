from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounting.models import (
    Account,
    AccountType,
    FiscalPeriod,
    JournalStatus,
    NormalBalance,
)
from apps.accounting.selectors import trial_balance
from apps.accounting.services import create_journal, post_journal, reverse_journal
from apps.identity.models import Membership, Organization, Role, User, LegalEntity


@pytest.fixture
def accounting_context():
    user = User.objects.create_user(email="finance@example.com", password="safe-test-password")
    organization = Organization.objects.create(name="Example", slug="example")
    entity = LegalEntity.objects.create(
        organization=organization,
        name="Example Ltd",
        slug="example-ltd",
        base_currency="USD",
    )
    membership = Membership.objects.create(
        organization=organization,
        user=user,
        role=Role.FINANCE_MANAGER,
        all_legal_entities=True,
    )
    cash = Account.objects.create(
        legal_entity=entity,
        code="1000",
        name="Cash",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        system_code="CASH",
    )
    equity = Account.objects.create(
        legal_entity=entity,
        code="3000",
        name="Owner Equity",
        account_type=AccountType.EQUITY,
        normal_balance=NormalBalance.CREDIT,
    )
    FiscalPeriod.objects.create(
        legal_entity=entity,
        name="2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    return membership, entity, cash, equity


@pytest.mark.django_db
def test_balanced_journal_posts_and_reports(accounting_context):
    membership, entity, cash, equity = accounting_context
    journal = create_journal(
        membership=membership,
        legal_entity=entity,
        entry_date=date(2026, 9, 17),
        memo="Opening capital",
        lines=[
            {"account_id": cash.id, "debit": Decimal("1000"), "credit": Decimal("0")},
            {"account_id": equity.id, "debit": Decimal("0"), "credit": Decimal("1000")},
        ],
    )
    post_journal(membership=membership, journal=journal)
    journal.refresh_from_db()
    assert journal.status == JournalStatus.POSTED
    rows = trial_balance(entity, end_date=date(2026, 9, 30))
    assert sum(row["debit"] for row in rows) == Decimal("1000")
    assert sum(row["credit"] for row in rows) == Decimal("1000")


@pytest.mark.django_db
def test_unbalanced_journal_rolls_back(accounting_context):
    membership, entity, cash, equity = accounting_context
    with pytest.raises(ValidationError):
        create_journal(
            membership=membership,
            legal_entity=entity,
            entry_date=date(2026, 9, 17),
            memo="Broken",
            lines=[
                {"account_id": cash.id, "debit": Decimal("100"), "credit": Decimal("0")},
                {"account_id": equity.id, "debit": Decimal("0"), "credit": Decimal("90")},
            ],
        )


@pytest.mark.django_db
def test_reversal_creates_equal_opposite_posting(accounting_context):
    membership, entity, cash, equity = accounting_context
    journal = create_journal(
        membership=membership,
        legal_entity=entity,
        entry_date=date(2026, 9, 17),
        memo="Capital",
        lines=[
            {"account_id": cash.id, "debit": Decimal("250"), "credit": Decimal("0")},
            {"account_id": equity.id, "debit": Decimal("0"), "credit": Decimal("250")},
        ],
    )
    post_journal(membership=membership, journal=journal)
    reversal = reverse_journal(
        membership=membership,
        journal=journal,
        reversal_date=date(2026, 9, 18),
    )
    assert reversal.status == JournalStatus.POSTED
    journal.refresh_from_db()
    assert journal.status == JournalStatus.REVERSED
    rows = trial_balance(entity, end_date=date(2026, 9, 30))
    assert all(row["balance"] == Decimal("0") for row in rows)
