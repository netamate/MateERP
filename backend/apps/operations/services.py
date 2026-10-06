import calendar
from datetime import date, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.audit.services import record_audit_event
from apps.identity.models import Membership
from apps.identity.policy import Permission, has_permission

from .models import BillingCycle, Subscription, SubscriptionPayment


def _require_permission(membership: Membership, permission: Permission) -> None:
    if not has_permission(membership, permission):
        raise PermissionDenied("You do not have permission for this operations action.")


def _require_entity_scope(membership: Membership, legal_entity) -> None:
    if legal_entity.organization_id != membership.organization_id:
        raise PermissionDenied("Cross-organization operations access is not allowed.")
    if membership.all_legal_entities:
        return
    if not membership.legal_entities.filter(id=legal_entity.id).exists():
        raise PermissionDenied("You do not have access to this legal entity.")


def audit_operations_change(
    *,
    membership: Membership,
    legal_entity,
    action: str,
    object_type: str,
    object_id,
    state: dict,
    request=None,
) -> None:
    record_audit_event(
        actor=membership.user,
        organization=membership.organization,
        legal_entity=legal_entity,
        action=action,
        object_type=object_type,
        object_id=object_id,
        new_state=state,
        request=request,
    )


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def next_subscription_due_date(subscription: Subscription, *, paid_on: date) -> date:
    base_date = subscription.next_renewal_date or paid_on
    if subscription.billing_cycle == BillingCycle.MONTHLY:
        return _add_months(base_date, 1)
    if subscription.billing_cycle == BillingCycle.QUARTERLY:
        return _add_months(base_date, 3)
    if subscription.billing_cycle == BillingCycle.SEMIANNUAL:
        return _add_months(base_date, 6)
    if subscription.billing_cycle == BillingCycle.ANNUAL:
        return _add_months(base_date, 12)
    if subscription.billing_cycle == BillingCycle.CUSTOM:
        if not subscription.custom_cycle_days:
            raise ValidationError("Custom billing cycle is missing its day interval.")
        return base_date + timedelta(days=subscription.custom_cycle_days)
    raise ValidationError("Unsupported subscription billing cycle.")


@transaction.atomic
def record_subscription_payment(
    *,
    membership: Membership,
    subscription: Subscription,
    paid_on: date,
    amount=None,
    currency: str | None = None,
    reference: str = "",
    notes: str = "",
    request=None,
) -> SubscriptionPayment:
    _require_permission(membership, Permission.MANAGE_OPERATIONS)
    _require_entity_scope(membership, subscription.legal_entity)

    payment_amount = subscription.amount if amount is None else amount
    payment_currency = subscription.currency if not currency else currency.upper()
    if payment_amount < 0:
        raise ValidationError("Payment amount cannot be negative.")

    previous_due_date = subscription.next_renewal_date
    next_due_date = next_subscription_due_date(subscription, paid_on=paid_on)

    payment = SubscriptionPayment.objects.create(
        legal_entity=subscription.legal_entity,
        subscription=subscription,
        paid_on=paid_on,
        previous_due_date=previous_due_date,
        next_due_date=next_due_date,
        amount=payment_amount,
        currency=payment_currency,
        reference=reference,
        notes=notes,
        created_by=membership.user,
    )

    subscription.next_renewal_date = next_due_date
    subscription.amount = payment_amount
    subscription.currency = payment_currency
    subscription.save(
        update_fields=["next_renewal_date", "amount", "currency", "updated_at"]
    )

    audit_operations_change(
        membership=membership,
        legal_entity=subscription.legal_entity,
        action="operations.subscription_paid",
        object_type="Subscription",
        object_id=subscription.id,
        state={
            "payment_id": str(payment.id),
            "paid_on": str(payment.paid_on),
            "previous_due_date": (
                str(payment.previous_due_date) if payment.previous_due_date else None
            ),
            "next_due_date": str(payment.next_due_date),
            "amount": str(payment.amount),
            "currency": payment.currency,
            "reference": payment.reference,
        },
        request=request,
    )
    return payment
