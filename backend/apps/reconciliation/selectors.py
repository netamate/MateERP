from decimal import Decimal

from django.db.models import Q

from apps.accounting.models import JournalLine, JournalStatus
from apps.finance.models import FinancialAccountType

from .models import AccountReconciliation, ReconciliationItem, ReconciliationStatus


LEDGER_STATUSES = [JournalStatus.POSTED, JournalStatus.REVERSED]


def _signed_amount(line, financial_account):
    if financial_account.account_type == FinancialAccountType.CREDIT_CARD:
        return line.credit - line.debit
    return line.debit - line.credit


def reconciliation_candidates(reconciliation: AccountReconciliation):
    account = reconciliation.financial_account
    queryset = (
        JournalLine.objects.filter(
            journal_entry__legal_entity=reconciliation.legal_entity,
            journal_entry__status__in=LEDGER_STATUSES,
            journal_entry__entry_date__lte=reconciliation.end_date,
            account=account.ledger_account,
            currency=account.currency,
        )
        .select_related("journal_entry", "account")
        .order_by("journal_entry__entry_date", "created_at")
    )
    queryset = queryset.filter(
        Q(reconciliation_item__isnull=True)
        | Q(reconciliation_item__reconciliation=reconciliation)
    )
    selected_ids = set(reconciliation.items.values_list("journal_line_id", flat=True))
    return [
        {
            "id": str(line.id),
            "journal_id": str(line.journal_entry_id),
            "journal_number": line.journal_entry.number,
            "date": line.journal_entry.entry_date,
            "source_type": line.journal_entry.source_type,
            "source_id": line.journal_entry.source_id,
            "description": line.description or line.journal_entry.memo,
            "debit": line.debit,
            "credit": line.credit,
            "currency": line.currency,
            "signed_amount": _signed_amount(line, account),
            "selected": line.id in selected_ids,
        }
        for line in queryset
    ]


def reconciliation_summary(reconciliation: AccountReconciliation):
    account = reconciliation.financial_account
    prior_items = ReconciliationItem.objects.filter(
        reconciliation__financial_account=account,
        reconciliation__status=ReconciliationStatus.COMPLETED,
    ).exclude(reconciliation=reconciliation)
    prior_items = prior_items.select_related("journal_line")
    prior_balance = sum(
        (_signed_amount(item.journal_line, account) for item in prior_items),
        Decimal("0"),
    )
    current_items = reconciliation.items.select_related("journal_line")
    current_movement = sum(
        (_signed_amount(item.journal_line, account) for item in current_items),
        Decimal("0"),
    )
    calculated = prior_balance + current_movement
    difference = reconciliation.statement_ending_balance - calculated
    candidate_count = len(reconciliation_candidates(reconciliation))
    return {
        "reconciliation_id": str(reconciliation.id),
        "currency": account.currency,
        "previously_reconciled_balance": prior_balance,
        "selected_movement": current_movement,
        "calculated_ending_balance": calculated,
        "statement_ending_balance": reconciliation.statement_ending_balance,
        "difference": difference,
        "selected_count": current_items.count(),
        "candidate_count": candidate_count,
    }
