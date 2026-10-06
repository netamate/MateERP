from datetime import date, timedelta

from .models import OperationalStatus, Subscription


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
