import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.audit.services import record_audit_event
from apps.identity.models import Membership
from apps.identity.policy import Permission, has_permission
from apps.notifications.models import Notification, NotificationKind
from apps.notifications.services import resolve_notifications

from .models import (
    BillingCycle,
    BillingInvoiceStatus,
    BillingPayment,
    BillingPaymentAllocation,
    Subscription,
    SubscriptionBillingPeriod,
    SubscriptionInvoice,
    SubscriptionPayment,
)


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
    subscription.save(update_fields=["next_renewal_date", "amount", "currency", "updated_at"])

    resolve_notifications(
        Notification.objects.filter(
            legal_entity=subscription.legal_entity,
            kind=NotificationKind.RENEWAL_DUE,
            resolved_at__isnull=True,
        ).filter(
            Q(dedupe_key__startswith=f"{subscription.id}:")
            | Q(dedupe_key__contains=f":{subscription.id}:")
        )
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


def _refresh_invoice_status(invoice: SubscriptionInvoice) -> SubscriptionInvoice:
    if invoice.status == BillingInvoiceStatus.VOID:
        return invoice
    paid = (
        invoice.payment_allocations.aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )
    if paid <= 0:
        next_status = BillingInvoiceStatus.OPEN
    elif paid < invoice.total_amount:
        next_status = BillingInvoiceStatus.PARTIALLY_PAID
    else:
        next_status = BillingInvoiceStatus.PAID
    if invoice.status != next_status:
        invoice.status = next_status
        invoice.save(update_fields=["status", "updated_at"])
    return invoice


@transaction.atomic
def create_billing_period(
    *,
    membership: Membership,
    subscription: Subscription,
    period_start,
    period_end,
    estimated_cost=None,
    current_usage_amount=Decimal("0"),
    usage_quantity=None,
    usage_unit="",
    notes="",
    request=None,
) -> SubscriptionBillingPeriod:
    _require_permission(membership, Permission.MANAGE_OPERATIONS)
    _require_entity_scope(membership, subscription.legal_entity)
    estimate = (
        subscription.estimated_cost
        if estimated_cost is None
        else estimated_cost
    )
    if estimate == Decimal("0") and subscription.billing_mode == "FIXED":
        estimate = subscription.amount
    period = SubscriptionBillingPeriod.objects.create(
        legal_entity=subscription.legal_entity,
        subscription=subscription,
        period_start=period_start,
        period_end=period_end,
        estimated_cost=estimate,
        current_usage_amount=current_usage_amount,
        usage_quantity=usage_quantity,
        usage_unit=usage_unit or subscription.usage_unit,
        current_usage_updated_at=(
            timezone.now()
            if current_usage_amount or usage_quantity is not None
            else None
        ),
        notes=notes,
        created_by=membership.user,
    )
    audit_operations_change(
        membership=membership,
        legal_entity=subscription.legal_entity,
        action="operations.billing_period_created",
        object_type="SubscriptionBillingPeriod",
        object_id=period.id,
        state={
            "subscription_id": str(subscription.id),
            "period_start": str(period.period_start),
            "period_end": str(period.period_end),
            "estimated_cost": str(period.estimated_cost),
            "current_usage_amount": str(period.current_usage_amount),
        },
        request=request,
    )
    return period


@transaction.atomic
def update_billing_period(
    *,
    membership: Membership,
    period: SubscriptionBillingPeriod,
    data: dict,
    request=None,
) -> SubscriptionBillingPeriod:
    _require_permission(membership, Permission.MANAGE_OPERATIONS)
    _require_entity_scope(membership, period.legal_entity)
    period = SubscriptionBillingPeriod.objects.select_for_update().get(pk=period.pk)
    usage_changed = False
    for field in (
        "period_start",
        "period_end",
        "estimated_cost",
        "current_usage_amount",
        "usage_quantity",
        "usage_unit",
        "is_closed",
        "notes",
    ):
        if field in data:
            setattr(period, field, data[field])
            if field in {"current_usage_amount", "usage_quantity"}:
                usage_changed = True
    if usage_changed:
        period.current_usage_updated_at = timezone.now()
    period.save()
    audit_operations_change(
        membership=membership,
        legal_entity=period.legal_entity,
        action="operations.billing_period_updated",
        object_type="SubscriptionBillingPeriod",
        object_id=period.id,
        state={
            "estimated_cost": str(period.estimated_cost),
            "current_usage_amount": str(period.current_usage_amount),
            "usage_quantity": (
                str(period.usage_quantity)
                if period.usage_quantity is not None
                else None
            ),
            "is_closed": period.is_closed,
        },
        request=request,
    )
    return period


@transaction.atomic
def create_subscription_invoice(
    *,
    membership: Membership,
    billing_period: SubscriptionBillingPeriod,
    invoice_number: str,
    invoice_date,
    currency: str,
    subtotal,
    tax_amount,
    total_amount,
    vendor=None,
    due_date=None,
    document=None,
    expense=None,
    notes="",
    request=None,
) -> SubscriptionInvoice:
    _require_permission(membership, Permission.MANAGE_OPERATIONS)
    _require_entity_scope(membership, billing_period.legal_entity)
    vendor = vendor or billing_period.subscription.vendor
    if vendor is None:
        raise ValidationError("Choose a vendor before recording an invoice.")
    invoice = SubscriptionInvoice.objects.create(
        legal_entity=billing_period.legal_entity,
        billing_period=billing_period,
        vendor=vendor,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        due_date=due_date,
        currency=currency,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount,
        document=document,
        expense=expense,
        notes=notes,
        created_by=membership.user,
    )
    audit_operations_change(
        membership=membership,
        legal_entity=invoice.legal_entity,
        action="operations.subscription_invoice_created",
        object_type="SubscriptionInvoice",
        object_id=invoice.id,
        state={
            "billing_period_id": str(billing_period.id),
            "invoice_number": invoice.invoice_number,
            "total_amount": str(invoice.total_amount),
            "currency": invoice.currency,
            "document_id": str(invoice.document_id) if invoice.document_id else None,
            "expense_id": str(invoice.expense_id) if invoice.expense_id else None,
        },
        request=request,
    )
    return invoice


@transaction.atomic
def update_subscription_invoice(
    *,
    membership: Membership,
    invoice: SubscriptionInvoice,
    data: dict,
    request=None,
) -> SubscriptionInvoice:
    _require_permission(membership, Permission.MANAGE_OPERATIONS)
    _require_entity_scope(membership, invoice.legal_entity)
    invoice = SubscriptionInvoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status == BillingInvoiceStatus.VOID:
        raise ValidationError("Voided invoices cannot be edited.")
    has_allocations = invoice.payment_allocations.exists()
    protected_amount_fields = {"subtotal", "tax_amount", "total_amount", "currency"}
    if has_allocations and protected_amount_fields.intersection(data):
        raise ValidationError(
            "Invoice amount and currency cannot change after payment allocation."
        )
    for field in (
        "invoice_number",
        "invoice_date",
        "due_date",
        "currency",
        "subtotal",
        "tax_amount",
        "total_amount",
        "document",
        "expense",
        "notes",
    ):
        if field in data:
            setattr(invoice, field, data[field])
    invoice.save()
    _refresh_invoice_status(invoice)
    audit_operations_change(
        membership=membership,
        legal_entity=invoice.legal_entity,
        action="operations.subscription_invoice_updated",
        object_type="SubscriptionInvoice",
        object_id=invoice.id,
        state={
            "invoice_number": invoice.invoice_number,
            "total_amount": str(invoice.total_amount),
            "document_id": str(invoice.document_id) if invoice.document_id else None,
            "expense_id": str(invoice.expense_id) if invoice.expense_id else None,
        },
        request=request,
    )
    return invoice


@transaction.atomic
def void_subscription_invoice(
    *,
    membership: Membership,
    invoice: SubscriptionInvoice,
    request=None,
) -> SubscriptionInvoice:
    _require_permission(membership, Permission.MANAGE_OPERATIONS)
    _require_entity_scope(membership, invoice.legal_entity)
    invoice = SubscriptionInvoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.payment_allocations.exists():
        raise ValidationError("Allocated invoices cannot be voided.")
    invoice.status = BillingInvoiceStatus.VOID
    invoice.save(update_fields=["status", "updated_at"])
    audit_operations_change(
        membership=membership,
        legal_entity=invoice.legal_entity,
        action="operations.subscription_invoice_voided",
        object_type="SubscriptionInvoice",
        object_id=invoice.id,
        state={"status": invoice.status},
        request=request,
    )
    return invoice


@transaction.atomic
def create_billing_payment(
    *,
    membership: Membership,
    subscription: Subscription,
    paid_on,
    amount,
    currency,
    reference="",
    financial_account=None,
    expense_payment=None,
    notes="",
    request=None,
) -> BillingPayment:
    _require_permission(membership, Permission.MANAGE_OPERATIONS)
    _require_entity_scope(membership, subscription.legal_entity)
    payment = BillingPayment.objects.create(
        legal_entity=subscription.legal_entity,
        subscription=subscription,
        paid_on=paid_on,
        amount=amount,
        currency=currency,
        reference=reference,
        financial_account=financial_account,
        expense_payment=expense_payment,
        notes=notes,
        created_by=membership.user,
    )
    audit_operations_change(
        membership=membership,
        legal_entity=payment.legal_entity,
        action="operations.billing_payment_created",
        object_type="BillingPayment",
        object_id=payment.id,
        state={
            "subscription_id": str(subscription.id),
            "payment_code": payment.payment_code,
            "amount": str(payment.amount),
            "currency": payment.currency,
            "expense_payment_id": (
                str(payment.expense_payment_id)
                if payment.expense_payment_id
                else None
            ),
        },
        request=request,
    )
    return payment


@transaction.atomic
def replace_billing_payment_allocations(
    *,
    membership: Membership,
    payment: BillingPayment,
    allocations: list[dict],
    request=None,
) -> BillingPayment:
    _require_permission(membership, Permission.MANAGE_OPERATIONS)
    _require_entity_scope(membership, payment.legal_entity)
    payment = BillingPayment.objects.select_for_update().get(pk=payment.pk)
    invoice_ids = [item["invoice"].id for item in allocations]
    if len(invoice_ids) != len(set(invoice_ids)):
        raise ValidationError("Each invoice can appear only once in a payment allocation.")

    requested_total = sum(
        (item["amount"] for item in allocations),
        Decimal("0"),
    )
    if requested_total > payment.amount:
        raise ValidationError("Allocation total exceeds the payment amount.")

    old_invoices = list(
        SubscriptionInvoice.objects.filter(
            payment_allocations__payment=payment
        ).distinct()
    )
    payment.allocations.all().delete()
    created = []
    for item in allocations:
        invoice = SubscriptionInvoice.objects.select_for_update().get(
            pk=item["invoice"].pk
        )
        if invoice.status == BillingInvoiceStatus.VOID:
            raise ValidationError("Voided invoices cannot receive payment allocations.")
        allocation = BillingPaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice,
            amount=item["amount"],
        )
        created.append(allocation)

    touched = {invoice.id: invoice for invoice in old_invoices}
    for allocation in created:
        touched[allocation.invoice_id] = allocation.invoice
    for invoice in touched.values():
        _refresh_invoice_status(invoice)

    allocated = (
        payment.allocations.aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )
    audit_operations_change(
        membership=membership,
        legal_entity=payment.legal_entity,
        action="operations.billing_payment_allocated",
        object_type="BillingPayment",
        object_id=payment.id,
        state={
            "allocated_amount": str(allocated),
            "unallocated_amount": str(payment.amount - allocated),
            "invoice_ids": [str(item["invoice"].id) for item in allocations],
        },
        request=request,
    )
    return payment
