from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.audit.services import record_audit_event
from apps.finance.models import Expense, ExpenseStatus
from apps.identity.models import Membership
from apps.identity.policy import Permission, has_permission

from .models import ExpenseAllocation


def _require_permission(membership: Membership, permission: Permission) -> None:
    if not has_permission(membership, permission):
        raise PermissionDenied("You do not have permission for this planning action.")


def _require_entity_scope(membership: Membership, legal_entity) -> None:
    if legal_entity.organization_id != membership.organization_id:
        raise PermissionDenied("Cross-organization planning access is not allowed.")
    if membership.all_legal_entities:
        return
    if not membership.legal_entities.filter(id=legal_entity.id).exists():
        raise PermissionDenied("You do not have access to this legal entity.")


def audit_planning_change(
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
def replace_expense_allocations(
    *,
    membership: Membership,
    expense: Expense,
    allocations: list[dict],
    request=None,
) -> list[ExpenseAllocation]:
    _require_permission(membership, Permission.MANAGE_PLANNING)
    _require_entity_scope(membership, expense.legal_entity)
    if expense.status != ExpenseStatus.DRAFT:
        raise ValidationError("Expense allocations can only be changed while the expense is draft.")

    total = sum((item["amount"] for item in allocations), Decimal("0"))
    if total > expense.amount:
        raise ValidationError("Allocated amount cannot exceed the expense amount.")

    for item in allocations:
        if item["amount"] <= 0:
            raise ValidationError("Allocation amount must be greater than zero.")
        if not any((item.get("cost_center"), item.get("product"), item.get("project"))):
            raise ValidationError("Each allocation requires at least one planning dimension.")
        for dimension in (item.get("cost_center"), item.get("product"), item.get("project")):
            if dimension and dimension.legal_entity_id != expense.legal_entity_id:
                raise ValidationError("Allocation dimensions must belong to the expense legal entity.")

    expense.allocations.all().delete()
    created = [
        ExpenseAllocation.objects.create(
            legal_entity=expense.legal_entity,
            expense=expense,
            created_by=membership.user,
            **item,
        )
        for item in allocations
    ]
    audit_planning_change(
        membership=membership,
        legal_entity=expense.legal_entity,
        action="planning.expense_allocations_replaced",
        object_type="Expense",
        object_id=expense.id,
        state={
            "allocation_count": len(created),
            "allocated_amount": str(total),
            "expense_amount": str(expense.amount),
        },
        request=request,
    )
    return created
