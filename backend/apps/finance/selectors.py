from decimal import Decimal

from apps.accounting.models import JournalStatus


def financial_account_transactions(financial_account):
    lines = (
        financial_account.ledger_account.journal_lines.filter(
            journal_entry__status__in=[JournalStatus.POSTED, JournalStatus.REVERSED],
        )
        .select_related("journal_entry")
        .order_by("journal_entry__entry_date", "created_at")
    )
    running = Decimal("0")
    result = []
    for line in lines:
        running += line.base_debit - line.base_credit
        result.append(
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
                "base_debit": line.base_debit,
                "base_credit": line.base_credit,
                "running_base_balance": running,
            }
        )
    return result
