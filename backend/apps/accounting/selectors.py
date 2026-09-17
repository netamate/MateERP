from decimal import Decimal

from django.db.models import Q, Sum

from .models import Account, AccountType, JournalLine, JournalStatus


def posted_lines(legal_entity, *, start_date=None, end_date=None):
    queryset = JournalLine.objects.filter(
        journal_entry__legal_entity=legal_entity,
        journal_entry__status__in=[JournalStatus.POSTED, JournalStatus.REVERSED],
    ).select_related("account", "journal_entry")
    if start_date:
        queryset = queryset.filter(journal_entry__entry_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(journal_entry__entry_date__lte=end_date)
    return queryset


def trial_balance(legal_entity, *, start_date=None, end_date=None):
    rows = (
        posted_lines(legal_entity, start_date=start_date, end_date=end_date)
        .values("account_id", "account__code", "account__name", "account__account_type")
        .annotate(debit=Sum("base_debit"), credit=Sum("base_credit"))
        .order_by("account__code")
    )
    result = []
    for row in rows:
        debit = row["debit"] or Decimal("0")
        credit = row["credit"] or Decimal("0")
        result.append({**row, "debit": debit, "credit": credit, "balance": debit - credit})
    return result


def _sum_account_type(rows, account_type, *, debit_normal):
    total = Decimal("0")
    for row in rows:
        if row["account__account_type"] != account_type:
            continue
        if debit_normal:
            total += row["debit"] - row["credit"]
        else:
            total += row["credit"] - row["debit"]
    return total


def profit_and_loss(legal_entity, *, start_date, end_date):
    rows = trial_balance(legal_entity, start_date=start_date, end_date=end_date)
    revenue = _sum_account_type(rows, AccountType.REVENUE, debit_normal=False)
    expenses = _sum_account_type(rows, AccountType.EXPENSE, debit_normal=True)
    return {"revenue": revenue, "expenses": expenses, "net_income": revenue - expenses}


def balance_sheet(legal_entity, *, as_of):
    rows = trial_balance(legal_entity, end_date=as_of)
    assets = _sum_account_type(rows, AccountType.ASSET, debit_normal=True)
    liabilities = _sum_account_type(rows, AccountType.LIABILITY, debit_normal=False)
    equity = _sum_account_type(rows, AccountType.EQUITY, debit_normal=False)
    retained = profit_and_loss(legal_entity, start_date=None, end_date=as_of)["net_income"]
    return {
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "retained_earnings": retained,
        "liabilities_and_equity": liabilities + equity + retained,
    }


def cash_flow_summary(legal_entity, *, start_date, end_date):
    cash_accounts = Account.objects.filter(
        legal_entity=legal_entity,
        is_active=True,
    ).filter(Q(system_code__icontains="CASH") | Q(system_code__icontains="BANK"))
    lines = posted_lines(legal_entity, start_date=start_date, end_date=end_date).filter(
        account__in=cash_accounts
    )
    totals = lines.aggregate(debit=Sum("base_debit"), credit=Sum("base_credit"))
    inflow = totals["debit"] or Decimal("0")
    outflow = totals["credit"] or Decimal("0")
    return {
        "cash_inflow": inflow,
        "cash_outflow": outflow,
        "net_cash_change": inflow - outflow,
    }
