from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.audit.services import record_audit_event
from apps.finance.services import create_expense
from apps.identity.models import Membership
from apps.identity.policy import Permission, has_permission

from .models import Domain, DomainRenewal


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


@transaction.atomic
def renew_domain(
    *,
    membership: Membership,
    domain: Domain,
    renewed_on,
    new_expiry_date,
    amount,
    currency,
    fx_rate,
    notes: str = "",
    generate_expense: bool = False,
    request=None,
) -> DomainRenewal:
    _require_permission(membership, Permission.MANAGE_OPERATIONS)
    _require_entity_scope(membership, domain.legal_entity)
    if new_expiry_date <= domain.expiry_date:
        raise ValidationError("New expiry date must be after the current domain expiry date.")
    if amount < 0 or fx_rate <= 0:
        raise ValidationError("Renewal amount cannot be negative and FX rate must be positive.")

    expense = None
    if generate_expense:
        if not domain.expense_account_id or not domain.payable_account_id:
            raise ValidationError(
                "Domain expense and payable accounts are required to generate an expense."
            )
        expense = create_expense(
            membership=membership,
            legal_entity=domain.legal_entity,
            request=request,
            vendor=None,
            expense_date=renewed_on,
            due_date=renewed_on,
            description=f"Domain renewal: {domain.domain_name}",
            reference=domain.domain_name,
            amount=amount,
            tax_amount=0,
            currency=currency,
            fx_rate=fx_rate,
            expense_account=domain.expense_account,
            payable_account=domain.payable_account,
            tax_code=None,
        )

    renewal = DomainRenewal.objects.create(
        legal_entity=domain.legal_entity,
        domain=domain,
        expense=expense,
        renewed_on=renewed_on,
        previous_expiry_date=domain.expiry_date,
        new_expiry_date=new_expiry_date,
        amount=amount,
        currency=currency,
        fx_rate=fx_rate,
        notes=notes,
        created_by=membership.user,
    )
    domain.expiry_date = new_expiry_date
    domain.renewal_amount = amount
    domain.currency = currency
    domain.save(update_fields=["expiry_date", "renewal_amount", "currency", "updated_at"])

    audit_operations_change(
        membership=membership,
        legal_entity=domain.legal_entity,
        action="operations.domain_renewed",
        object_type="Domain",
        object_id=domain.id,
        state={
            "previous_expiry_date": str(renewal.previous_expiry_date),
            "new_expiry_date": str(renewal.new_expiry_date),
            "amount": str(renewal.amount),
            "currency": renewal.currency,
            "expense_id": str(expense.id) if expense else None,
        },
        request=request,
    )
    return renewal
