from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import (
    BillingInvoiceStatus,
    BillingPeriodStatus,
    BillingPayment,
    OperationalStatus,
    Subscription,
    SubscriptionBillingPeriod,
)


def renewal_calendar(legal_entity, *, start_date=None, end_date=None):
    start = start_date or date.today()
    end = end_date or (start + timedelta(days=90))

    subscriptions = Subscription.objects.filter(
        legal_entity=legal_entity,
        status=OperationalStatus.ACTIVE,
        next_renewal_date__isnull=False,
        next_renewal_date__gte=start,
        next_renewal_date__lte=end,
    ).select_related("vendor")

    rows = [
        {
            "source_type": "SUBSCRIPTION",
            "source_id": str(subscription.id),
            "service_type": subscription.service_type,
            "name": subscription.name,
            "renewal_date": subscription.next_renewal_date,
            "amount": subscription.amount,
            "currency": subscription.currency,
            "auto_renew": subscription.auto_renew,
            "vendor_name": subscription.vendor.name if subscription.vendor else None,
            "reference": subscription.reference,
            "payment_method": subscription.payment_method,
        }
        for subscription in subscriptions
    ]

    return sorted(rows, key=lambda row: (row["renewal_date"], row["name"]))


def invoice_paid_amount(invoice):
    return (
        invoice.payment_allocations.aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )


def billing_period_snapshot(period: SubscriptionBillingPeriod, *, today=None):
    today = today or timezone.localdate()
    invoices = list(
        period.invoices.exclude(status=BillingInvoiceStatus.VOID).prefetch_related(
            "payment_allocations"
        )
    )
    actual = sum((invoice.total_amount for invoice in invoices), Decimal("0"))
    paid = sum(
        (
            sum(
                (allocation.amount for allocation in invoice.payment_allocations.all()),
                Decimal("0"),
            )
            for invoice in invoices
        ),
        Decimal("0"),
    )
    if period.is_closed:
        status = BillingPeriodStatus.CLOSED
    elif actual > 0 and paid >= actual:
        status = BillingPeriodStatus.PAID
    elif actual > 0 and paid > 0:
        status = BillingPeriodStatus.PARTIALLY_PAID
    elif actual > 0:
        status = BillingPeriodStatus.INVOICED
    elif period.period_end < today:
        status = BillingPeriodStatus.AWAITING_INVOICE
    else:
        status = BillingPeriodStatus.OPEN

    budget = period.subscription.monthly_budget
    tracked_cost = max(period.current_usage_amount, actual)
    budget_percent = None
    thresholds_reached = []
    if budget and budget > 0:
        budget_percent = (tracked_cost / budget * Decimal("100")).quantize(
            Decimal("0.1")
        )
        thresholds_reached = [
            threshold
            for threshold in period.subscription.budget_alert_thresholds
            if budget_percent >= Decimal(str(threshold))
        ]

    return {
        "status": status,
        "estimated_cost": period.estimated_cost,
        "current_usage_amount": period.current_usage_amount,
        "actual_billed_amount": actual,
        "paid_amount": paid,
        "outstanding_amount": max(actual - paid, Decimal("0")),
        "variance_from_estimate": actual - period.estimated_cost,
        "monthly_budget": budget,
        "budget_percent": budget_percent,
        "budget_thresholds_reached": thresholds_reached,
        "over_budget": bool(budget and tracked_cost > budget),
        "missing_invoice": bool(period.period_end < today and actual == 0),
        "invoice_count": len(invoices),
    }


def billing_dashboard(legal_entity):
    periods = list(
        SubscriptionBillingPeriod.objects.filter(legal_entity=legal_entity)
        .select_related(
            "subscription",
            "subscription__vendor",
            "subscription__service",
            "subscription__service_account",
        )
        .prefetch_related("invoices__payment_allocations")
        .order_by("period_end")
    )
    snapshots = [(period, billing_period_snapshot(period)) for period in periods]

    totals_by_currency = {}
    trend_map = {}
    for period, snapshot in snapshots:
        currency = period.subscription.currency
        totals = totals_by_currency.setdefault(
            currency,
            {
                "currency": currency,
                "estimated_cost": Decimal("0"),
                "current_usage_amount": Decimal("0"),
                "actual_billed_amount": Decimal("0"),
                "paid_amount": Decimal("0"),
                "outstanding_amount": Decimal("0"),
            },
        )
        for field in (
            "estimated_cost",
            "current_usage_amount",
            "actual_billed_amount",
            "paid_amount",
            "outstanding_amount",
        ):
            totals[field] += snapshot[field]

        key = (period.period_end.strftime("%Y-%m"), currency)
        row = trend_map.setdefault(
            key,
            {
                "period": key[0],
                "currency": currency,
                "estimated_cost": Decimal("0"),
                "current_usage_amount": Decimal("0"),
                "actual_billed_amount": Decimal("0"),
                "paid_amount": Decimal("0"),
                "budget": Decimal("0"),
            },
        )
        row["estimated_cost"] += snapshot["estimated_cost"]
        row["current_usage_amount"] += snapshot["current_usage_amount"]
        row["actual_billed_amount"] += snapshot["actual_billed_amount"]
        row["paid_amount"] += snapshot["paid_amount"]
        row["budget"] += period.subscription.monthly_budget or Decimal("0")

    unallocated_by_currency = {}
    for payment in BillingPayment.objects.filter(legal_entity=legal_entity).prefetch_related(
        "allocations"
    ):
        allocated = sum(
            (allocation.amount for allocation in payment.allocations.all()),
            Decimal("0"),
        )
        remaining = max(payment.amount - allocated, Decimal("0"))
        unallocated_by_currency[payment.currency] = (
            unallocated_by_currency.get(payment.currency, Decimal("0")) + remaining
        )

    invoices = (
        legal_entity.subscription_invoices.exclude(status=BillingInvoiceStatus.VOID)
        .select_related("expense")
        .prefetch_related("payment_allocations")
    )
    unreconciled_invoices = 0
    unpaid_invoice_count = 0
    for invoice in invoices:
        paid = sum(
            (allocation.amount for allocation in invoice.payment_allocations.all()),
            Decimal("0"),
        )
        if paid < invoice.total_amount:
            unpaid_invoice_count += 1
        if invoice.expense_id is None:
            unreconciled_invoices += 1
        elif (
            invoice.expense.currency != invoice.currency
            or invoice.expense.amount != invoice.total_amount
        ):
            unreconciled_invoices += 1

    return {
        "totals_by_currency": list(totals_by_currency.values()),
        "missing_invoice_count": sum(
            1 for _, snapshot in snapshots if snapshot["missing_invoice"]
        ),
        "over_budget_period_count": sum(
            1 for _, snapshot in snapshots if snapshot["over_budget"]
        ),
        "unpaid_invoice_count": unpaid_invoice_count,
        "unreconciled_invoice_count": unreconciled_invoices,
        "unallocated_payment_by_currency": [
            {"currency": currency, "amount": amount}
            for currency, amount in sorted(unallocated_by_currency.items())
        ],
        "trend": list(trend_map.values())[-24:],
    }

