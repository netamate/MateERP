from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from apps.accounting.models import AccountType, JournalLine, JournalStatus
from apps.accounting.selectors import cash_flow_summary, profit_and_loss, trial_balance
from apps.automation.models import AutomationPolicy, AutomationRun, RunStatus, SyncStatus, VendorIntegration
from apps.finance.models import Expense, FounderFunding, Income, RecordStatus
from apps.operations.models import (
    BillingInvoiceStatus,
    BillingMode,
    BillingPayment,
    SubscriptionBillingPeriod,
    SubscriptionInvoice,
)
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


def _billing_periods_in_range(legal_entity, *, start_date=None, end_date=None):
    queryset = (
        SubscriptionBillingPeriod.objects.filter(legal_entity=legal_entity)
        .select_related("subscription", "subscription__vendor")
        .prefetch_related("invoices__payment_allocations")
    )
    if start_date:
        queryset = queryset.filter(period_end__gte=start_date)
    if end_date:
        queryset = queryset.filter(period_start__lte=end_date)
    return queryset


def _period_actuals(period):
    invoices = [
        invoice
        for invoice in period.invoices.all()
        if invoice.status != BillingInvoiceStatus.VOID
    ]
    billed = sum((invoice.total_amount for invoice in invoices), Decimal("0"))
    paid = sum(
        (
            allocation.amount
            for invoice in invoices
            for allocation in invoice.payment_allocations.all()
        ),
        Decimal("0"),
    )
    return billed, paid


def _period_forecast(period, *, today):
    billed, _ = _period_actuals(period)
    tracked = max(period.current_usage_amount, billed)
    if period.is_closed or today > period.period_end:
        return tracked
    if today < period.period_start:
        return period.estimated_cost
    if tracked <= 0:
        return period.estimated_cost
    elapsed = max((today - period.period_start).days + 1, 1)
    total_days = max((period.period_end - period.period_start).days + 1, 1)
    projected = tracked / Decimal(elapsed) * Decimal(total_days)
    return max(tracked, projected).quantize(Decimal("0.01"))


def operations_cost_intelligence(legal_entity, *, start_date=None, end_date=None):
    today = timezone.localdate()
    periods = list(
        _billing_periods_in_range(
            legal_entity,
            start_date=start_date,
            end_date=end_date,
        )
    )

    currency_totals = defaultdict(
        lambda: {
            "estimated_cost": Decimal("0"),
            "current_usage": Decimal("0"),
            "actual_billed": Decimal("0"),
            "paid": Decimal("0"),
            "outstanding": Decimal("0"),
            "forecast": Decimal("0"),
            "budget": Decimal("0"),
        }
    )
    subscription_totals = {}
    vendor_totals = defaultdict(
        lambda: {
            "tracked_cost": Decimal("0"),
            "actual_billed": Decimal("0"),
            "forecast": Decimal("0"),
        }
    )
    monthly_totals = defaultdict(
        lambda: {
            "estimated_cost": Decimal("0"),
            "current_usage": Decimal("0"),
            "actual_billed": Decimal("0"),
            "paid": Decimal("0"),
            "forecast": Decimal("0"),
        }
    )

    for period in periods:
        subscription = period.subscription
        currency = subscription.currency
        billed, paid = _period_actuals(period)
        outstanding = max(billed - paid, Decimal("0"))
        forecast = _period_forecast(period, today=today)
        budget = subscription.monthly_budget or Decimal("0")
        tracked = max(period.current_usage_amount, billed)
        totals = currency_totals[currency]
        totals["estimated_cost"] += period.estimated_cost
        totals["current_usage"] += period.current_usage_amount
        totals["actual_billed"] += billed
        totals["paid"] += paid
        totals["outstanding"] += outstanding
        totals["forecast"] += forecast
        totals["budget"] += budget

        key = str(subscription.id)
        row = subscription_totals.setdefault(
            key,
            {
                "subscription_id": key,
                "subscription_code": subscription.subscription_code,
                "subscription_name": subscription.name,
                "vendor_id": str(subscription.vendor_id) if subscription.vendor_id else None,
                "vendor_name": subscription.vendor.name if subscription.vendor_id else None,
                "billing_mode": subscription.billing_mode,
                "currency": currency,
                "estimated_cost": Decimal("0"),
                "current_usage": Decimal("0"),
                "actual_billed": Decimal("0"),
                "paid": Decimal("0"),
                "outstanding": Decimal("0"),
                "forecast": Decimal("0"),
                "budget": Decimal("0"),
                "period_count": 0,
            },
        )
        row["estimated_cost"] += period.estimated_cost
        row["current_usage"] += period.current_usage_amount
        row["actual_billed"] += billed
        row["paid"] += paid
        row["outstanding"] += outstanding
        row["forecast"] += forecast
        row["budget"] += budget
        row["period_count"] += 1

        if subscription.vendor_id:
            vendor_key = (
                str(subscription.vendor_id),
                subscription.vendor.name,
                currency,
            )
            vendor_totals[vendor_key]["tracked_cost"] += tracked
            vendor_totals[vendor_key]["actual_billed"] += billed
            vendor_totals[vendor_key]["forecast"] += forecast

        month_key = (period.period_start.strftime("%Y-%m"), currency)
        month = monthly_totals[month_key]
        month["estimated_cost"] += period.estimated_cost
        month["current_usage"] += period.current_usage_amount
        month["actual_billed"] += billed
        month["paid"] += paid
        month["forecast"] += forecast

    currency_rows = []
    for currency, values in sorted(currency_totals.items()):
        currency_rows.append(
            {
                "currency": currency,
                **{key: str(value) for key, value in values.items()},
            }
        )

    subscription_rows = []
    for row in subscription_totals.values():
        budget = row["budget"]
        forecast = row["forecast"]
        subscription_rows.append(
            {
                **{
                    key: value
                    for key, value in row.items()
                    if key
                    not in {
                        "estimated_cost",
                        "current_usage",
                        "actual_billed",
                        "paid",
                        "outstanding",
                        "forecast",
                        "budget",
                    }
                },
                "estimated_cost": str(row["estimated_cost"]),
                "current_usage": str(row["current_usage"]),
                "actual_billed": str(row["actual_billed"]),
                "paid": str(row["paid"]),
                "outstanding": str(row["outstanding"]),
                "forecast": str(forecast),
                "budget": str(budget),
                "forecast_variance": str(forecast - budget if budget else Decimal("0")),
                "over_budget_forecast": bool(budget and forecast > budget),
            }
        )
    subscription_rows.sort(
        key=lambda item: (item["currency"], Decimal(item["forecast"])),
        reverse=True,
    )

    vendor_rows = [
        {
            "vendor_id": vendor_id,
            "vendor_name": vendor_name,
            "currency": currency,
            "tracked_cost": str(values["tracked_cost"]),
            "actual_billed": str(values["actual_billed"]),
            "forecast": str(values["forecast"]),
        }
        for (vendor_id, vendor_name, currency), values in vendor_totals.items()
    ]
    vendor_rows.sort(
        key=lambda item: (item["currency"], Decimal(item["forecast"])),
        reverse=True,
    )

    monthly_rows = [
        {
            "month": month,
            "currency": currency,
            **{key: str(value) for key, value in values.items()},
        }
        for (month, currency), values in sorted(monthly_totals.items())
    ]

    invoices = SubscriptionInvoice.objects.filter(
        legal_entity=legal_entity,
    ).exclude(status=BillingInvoiceStatus.VOID)
    if start_date:
        invoices = invoices.filter(invoice_date__gte=start_date)
    if end_date:
        invoices = invoices.filter(invoice_date__lte=end_date)
    invoice_rows = list(invoices.select_related("expense"))
    invoice_matched = 0
    invoice_mismatch = 0
    invoice_unmatched = 0
    for invoice in invoice_rows:
        if not invoice.expense_id:
            invoice_unmatched += 1
        elif (
            invoice.expense.currency == invoice.currency
            and invoice.expense.amount == invoice.total_amount
        ):
            invoice_matched += 1
        else:
            invoice_mismatch += 1

    payments = BillingPayment.objects.filter(legal_entity=legal_entity)
    if start_date:
        payments = payments.filter(paid_on__gte=start_date)
    if end_date:
        payments = payments.filter(paid_on__lte=end_date)
    payment_total = payments.count()
    payment_matched = payments.filter(expense_payment__isnull=False).count()

    integrations = VendorIntegration.objects.filter(
        legal_entity=legal_entity,
        enabled=True,
    )
    stale_before = timezone.now() - timedelta(hours=26)
    integration_total = integrations.count()
    integration_failed = integrations.filter(last_sync_status=SyncStatus.FAILED).count()
    integration_never = integrations.filter(last_sync_status=SyncStatus.NEVER).count()
    integration_stale = integrations.filter(
        last_sync_at__isnull=False,
        last_sync_at__lt=stale_before,
    ).count()

    enabled_policies = AutomationPolicy.objects.filter(
        organization=legal_entity.organization,
        enabled=True,
    ).filter(
        Q(legal_entity__isnull=True) | Q(legal_entity=legal_entity)
    )
    failures_24h = AutomationRun.objects.filter(
        policy__in=enabled_policies,
        status=RunStatus.FAILED,
        started_at__gte=timezone.now() - timedelta(hours=24),
    ).count()

    return {
        "currency_totals": currency_rows,
        "subscriptions": subscription_rows,
        "vendors": vendor_rows,
        "monthly_trend": monthly_rows,
        "reconciliation_health": {
            "invoice_total": len(invoice_rows),
            "invoice_matched": invoice_matched,
            "invoice_mismatch": invoice_mismatch,
            "invoice_unmatched": invoice_unmatched,
            "payment_total": payment_total,
            "payment_matched": payment_matched,
            "payment_unmatched": payment_total - payment_matched,
        },
        "integration_health": {
            "active": integration_total,
            "failed": integration_failed,
            "never_synced": integration_never,
            "stale": integration_stale,
        },
        "automation_health": {
            "enabled_policies": enabled_policies.count(),
            "failed_runs_24h": failures_24h,
        },
    }
