from datetime import date, timedelta

from .models import Domain, InfrastructureAsset, OperationalStatus, Subscription


def renewal_calendar(legal_entity, *, start_date=None, end_date=None):
    start = start_date or date.today()
    end = end_date or (start + timedelta(days=90))
    rows = []

    subscriptions = Subscription.objects.filter(
        legal_entity=legal_entity,
        status=OperationalStatus.ACTIVE,
        next_renewal_date__isnull=False,
        next_renewal_date__gte=start,
        next_renewal_date__lte=end,
    ).select_related("vendor", "product", "cost_center")
    for subscription in subscriptions:
        rows.append(
            {
                "source_type": "SUBSCRIPTION",
                "source_id": str(subscription.id),
                "name": subscription.name,
                "renewal_date": subscription.next_renewal_date,
                "amount": subscription.amount,
                "currency": subscription.currency,
                "auto_renew": subscription.auto_renew,
                "vendor_name": subscription.vendor.name if subscription.vendor else None,
                "product_name": subscription.product.name if subscription.product else None,
                "cost_center_name": (
                    subscription.cost_center.name if subscription.cost_center else None
                ),
            }
        )

    domains = Domain.objects.filter(
        legal_entity=legal_entity,
        status=OperationalStatus.ACTIVE,
        expiry_date__gte=start,
        expiry_date__lte=end,
    ).select_related("product")
    for domain in domains:
        rows.append(
            {
                "source_type": "DOMAIN",
                "source_id": str(domain.id),
                "name": domain.domain_name,
                "renewal_date": domain.expiry_date,
                "amount": domain.renewal_amount,
                "currency": domain.currency,
                "auto_renew": domain.auto_renew,
                "vendor_name": domain.registrar or None,
                "product_name": domain.product.name if domain.product else None,
                "cost_center_name": None,
            }
        )

    assets = InfrastructureAsset.objects.filter(
        legal_entity=legal_entity,
        status=OperationalStatus.ACTIVE,
        next_renewal_date__isnull=False,
        next_renewal_date__gte=start,
        next_renewal_date__lte=end,
    ).select_related("vendor", "product", "cost_center")
    for asset in assets:
        rows.append(
            {
                "source_type": "INFRASTRUCTURE",
                "source_id": str(asset.id),
                "name": asset.name,
                "renewal_date": asset.next_renewal_date,
                "amount": asset.renewal_amount,
                "currency": asset.currency,
                "auto_renew": asset.auto_renew,
                "vendor_name": asset.vendor.name if asset.vendor else None,
                "product_name": asset.product.name if asset.product else None,
                "cost_center_name": asset.cost_center.name if asset.cost_center else None,
            }
        )

    return sorted(rows, key=lambda row: (row["renewal_date"], row["source_type"], row["name"]))
