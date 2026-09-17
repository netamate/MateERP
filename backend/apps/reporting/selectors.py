from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum

from apps.accounting.models import AccountType, JournalLine, JournalStatus
from apps.accounting.selectors import cash_flow_summary, profit_and_loss, trial_balance
from apps.finance.models import Expense, FounderFunding, Income, RecordStatus
from apps.planning.models import ExpenseAllocation


POSTED_STATUSES = [JournalStatus.POSTED, JournalStatus.REVERSED]


def _in_range(queryset, field: str, *, start_date=None, end_date=None):
    if start_date:
        queryset = queryset.filter(**{f"{field}__gte": start_date})
    if end_date:
        queryset = queryset.filter(**{f"{field}__lte": end_date})
    return queryset


def posted_expenses(legal_entity, *, start_date=None, end_date=None):
    queryset = Expense.objects.filter(
        legal_entity=legal_entity,
        journal_entry__status=JournalStatus.POSTED,
    ).select_related("vendor", "expense_account", "journal_entry")
    return _in_range(queryset, "expense_date", start_date=start_date, end_date=end_date)


def posted_income(legal_entity, *, start_date=None, end_date=None):
    queryset = Income.objects.filter(
        legal_entity=legal_entity,
        status=RecordStatus.POSTED,
        journal_entry__status=JournalStatus.POSTED,
    ).select_related("revenue_account", "financial_account", "journal_entry")
    return _in_range(queryset, "income_date", start_date=start_date, end_date=end_date)


def expense_report(legal_entity, *, start_date=None, end_date=None):
    rows = []
    total = Decimal("0")
    for expense in posted_expenses(legal_entity, start_date=start_date, end_date=end_date):
        base_amount = (expense.amount * expense.fx_rate).quantize(Decimal("0.01"))
        total += base_amount
        rows.append(
            {
                "id": str(expense.id),
                "date": expense.expense_date,
                "description": expense.description,
                "vendor_id": str(expense.vendor_id) if expense.vendor_id else None,
                "vendor_name": expense.vendor.name if expense.vendor_id else None,
                "account_code": expense.expense_account.code,
                "account_name": expense.expense_account.name,
                "amount": expense.amount,
                "currency": expense.currency,
                "fx_rate": expense.fx_rate,
                "base_amount": base_amount,
            }
        )
    return {"base_currency": legal_entity.base_currency, "total": total, "rows": rows}


def revenue_report(legal_entity, *, start_date=None, end_date=None):
    rows = []
    total = Decimal("0")
    for income in posted_income(legal_entity, start_date=start_date, end_date=end_date):
        base_amount = (income.amount * income.fx_rate).quantize(Decimal("0.01"))
        total += base_amount
        rows.append(
            {
                "id": str(income.id),
                "date": income.income_date,
                "payer_name": income.payer_name,
                "description": income.description,
                "account_code": income.revenue_account.code,
                "account_name": income.revenue_account.name,
                "amount": income.amount,
                "currency": income.currency,
                "fx_rate": income.fx_rate,
                "base_amount": base_amount,
            }
        )
    return {"base_currency": legal_entity.base_currency, "total": total, "rows": rows}


def vendor_spend(legal_entity, *, start_date=None, end_date=None):
    totals: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    unattributed = Decimal("0")
    for expense in posted_expenses(legal_entity, start_date=start_date, end_date=end_date):
        base_amount = (expense.amount * expense.fx_rate).quantize(Decimal("0.01"))
        if expense.vendor_id:
            totals[(str(expense.vendor_id), expense.vendor.name)] += base_amount
        else:
            unattributed += base_amount
    rows = [
        {"vendor_id": vendor_id, "vendor_name": name, "base_amount": amount}
        for (vendor_id, name), amount in sorted(
            totals.items(), key=lambda item: item[1], reverse=True
        )
    ]
    return {
        "base_currency": legal_entity.base_currency,
        "total": sum((row["base_amount"] for row in rows), Decimal("0")) + unattributed,
        "unattributed": unattributed,
        "rows": rows,
    }


def _allocation_spend(legal_entity, dimension: str, *, start_date=None, end_date=None):
    queryset = ExpenseAllocation.objects.filter(
        legal_entity=legal_entity,
        expense__journal_entry__status=JournalStatus.POSTED,
    ).select_related(dimension, "expense")
    queryset = _in_range(
        queryset,
        "expense__expense_date",
        start_date=start_date,
        end_date=end_date,
    )
    totals: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for allocation in queryset:
        target = getattr(allocation, dimension)
        if target is not None:
            totals[(str(target.id), target.name)] += allocation.base_amount
    return [
        {
            f"{dimension}_id": dimension_id,
            f"{dimension}_name": name,
            "base_amount": amount,
        }
        for (dimension_id, name), amount in sorted(
            totals.items(), key=lambda item: item[1], reverse=True
        )
    ]


def product_cost(legal_entity, *, start_date=None, end_date=None):
    rows = _allocation_spend(
        legal_entity,
        "product",
        start_date=start_date,
        end_date=end_date,
    )
    return {
        "base_currency": legal_entity.base_currency,
        "total": sum((row["base_amount"] for row in rows), Decimal("0")),
        "rows": rows,
    }


def cost_center_spend(legal_entity, *, start_date=None, end_date=None):
    rows = _allocation_spend(
        legal_entity,
        "cost_center",
        start_date=start_date,
        end_date=end_date,
    )
    return {
        "base_currency": legal_entity.base_currency,
        "total": sum((row["base_amount"] for row in rows), Decimal("0")),
        "rows": rows,
    }


def account_balances(legal_entity, *, as_of=None):
    rows = trial_balance(legal_entity, end_date=as_of)
    result = []
    for row in rows:
        debit = row["debit"]
        credit = row["credit"]
        account_type = row["account__account_type"]
        debit_normal = account_type in {AccountType.ASSET, AccountType.EXPENSE}
        natural_balance = debit - credit if debit_normal else credit - debit
        result.append(
            {
                "account_id": str(row["account_id"]),
                "account_code": row["account__code"],
                "account_name": row["account__name"],
                "account_type": account_type,
                "debit": debit,
                "credit": credit,
                "natural_balance": natural_balance,
            }
        )
    return {"base_currency": legal_entity.base_currency, "rows": result}


def currency_exposure(legal_entity, *, as_of=None):
    queryset = JournalLine.objects.filter(
        journal_entry__legal_entity=legal_entity,
        journal_entry__status__in=POSTED_STATUSES,
        account__financial_account__isnull=False,
    )
    if as_of:
        queryset = queryset.filter(journal_entry__entry_date__lte=as_of)
    grouped = queryset.values("currency").annotate(
        debit=Sum("debit"),
        credit=Sum("credit"),
        base_debit=Sum("base_debit"),
        base_credit=Sum("base_credit"),
    )
    rows = []
    for row in grouped:
        debit = row["debit"] or Decimal("0")
        credit = row["credit"] or Decimal("0")
        base_debit = row["base_debit"] or Decimal("0")
        base_credit = row["base_credit"] or Decimal("0")
        rows.append(
            {
                "currency": row["currency"],
                "transaction_net": debit - credit,
                "base_net": base_debit - base_credit,
            }
        )
    rows.sort(key=lambda item: item["currency"])
    return {"base_currency": legal_entity.base_currency, "rows": rows}


def founder_capital(legal_entity, *, start_date=None, end_date=None):
    queryset = FounderFunding.objects.filter(
        legal_entity=legal_entity,
        status=RecordStatus.POSTED,
        journal_entry__status=JournalStatus.POSTED,
    )
    queryset = _in_range(
        queryset,
        "funding_date",
        start_date=start_date,
        end_date=end_date,
    )
    totals: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for funding in queryset:
        base_amount = (funding.amount * funding.fx_rate).quantize(Decimal("0.01"))
        totals[(funding.founder_name, funding.funding_type)] += base_amount
    rows = [
        {"founder_name": founder, "funding_type": funding_type, "base_amount": amount}
        for (founder, funding_type), amount in sorted(totals.items())
    ]
    return {
        "base_currency": legal_entity.base_currency,
        "total": sum((row["base_amount"] for row in rows), Decimal("0")),
        "rows": rows,
    }


def financial_overview(legal_entity, *, start_date=None, end_date=None):
    pnl = profit_and_loss(legal_entity, start_date=start_date, end_date=end_date)
    cash = cash_flow_summary(legal_entity, start_date=start_date, end_date=end_date)
    expenses = expense_report(legal_entity, start_date=start_date, end_date=end_date)
    revenue = revenue_report(legal_entity, start_date=start_date, end_date=end_date)
    return {
        "base_currency": legal_entity.base_currency,
        "revenue": pnl["revenue"],
        "expenses": pnl["expenses"],
        "net_income": pnl["net_income"],
        "cash_inflow": cash["cash_inflow"],
        "cash_outflow": cash["cash_outflow"],
        "net_cash_change": cash["net_cash_change"],
        "operational_expense_total": expenses["total"],
        "operational_revenue_total": revenue["total"],
    }
