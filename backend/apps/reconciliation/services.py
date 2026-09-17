from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import JournalLine, JournalStatus
from apps.audit.services import record_audit_event
from apps.identity.models import Membership
from apps.identity.policy import Permission, has_permission

from .models import AccountReconciliation, ReconciliationItem, ReconciliationStatus
from .selectors import reconciliation_summary


def _require_permission(membership: Membership, permission: Permission) -> None:
    if not has_permission(membership, permission):
        raise PermissionDenied("You do not have permission for this reconciliation action.")


def _require_entity_scope(membership: Membership, legal_entity) -> None:
    if legal_entity.organization_id != membership.organization_id:
        raise PermissionDenied("Cross-organization reconciliation access is not allowed.")
    if membership.all_legal_entities:
        return
    if not membership.legal_entities.filter(id=legal_entity.id).exists():
        raise PermissionDenied("You do not have access to this legal entity.")


def _audit(*, membership, reconciliation, action, state, request=None):
    record_audit_event(
        actor=membership.user,
        organization=membership.organization,
        legal_entity=reconciliation.legal_entity,
        action=action,
        object_type="AccountReconciliation",
        object_id=reconciliation.id,
        new_state=state,
        request=request,
    )


@transaction.atomic
def create_reconciliation(
    *,
    membership: Membership,
    legal_entity,
    financial_account,
    start_date,
    end_date,
    statement_ending_balance: Decimal,
    notes: str = "",
    request=None,
) -> AccountReconciliation:
    _require_permission(membership, Permission.MANAGE_RECONCILIATION)
    _require_entity_scope(membership, legal_entity)
    if financial_account.legal_entity_id != legal_entity.id:
        raise ValidationError("Financial account must belong to the active legal entity.")
    reconciliation = AccountReconciliation.objects.create(
        legal_entity=legal_entity,
        financial_account=financial_account,
        start_date=start_date,
        end_date=end_date,
        statement_ending_balance=statement_ending_balance,
        notes=notes,
        created_by=membership.user,
    )
    _audit(
        membership=membership,
        reconciliation=reconciliation,
        action="reconciliation.created",
        state={
            "financial_account_id": str(financial_account.id),
            "start_date": str(start_date),
            "end_date": str(end_date),
            "statement_ending_balance": str(statement_ending_balance),
        },
        request=request,
    )
    return reconciliation


@transaction.atomic
def replace_reconciliation_items(
    *,
    membership: Membership,
    reconciliation: AccountReconciliation,
    journal_line_ids: list,
    request=None,
) -> AccountReconciliation:
    _require_permission(membership, Permission.MANAGE_RECONCILIATION)
    _require_entity_scope(membership, reconciliation.legal_entity)
    reconciliation = AccountReconciliation.objects.select_for_update().get(pk=reconciliation.pk)
    if reconciliation.status != ReconciliationStatus.DRAFT:
        raise ValidationError("Completed reconciliations are immutable.")

    unique_ids = list(dict.fromkeys(journal_line_ids))
    lines = list(
        JournalLine.objects.filter(id__in=unique_ids)
        .select_related("journal_entry", "account")
        .order_by("journal_entry__entry_date", "created_at")
    )
    if len(lines) != len(unique_ids):
        raise ValidationError("One or more reconciliation journal lines do not exist.")

    existing_elsewhere = ReconciliationItem.objects.filter(journal_line_id__in=unique_ids).exclude(
        reconciliation=reconciliation
    )
    if existing_elsewhere.exists():
        raise ValidationError("One or more journal lines are already reconciled elsewhere.")

    account = reconciliation.financial_account
    for line in lines:
        if line.journal_entry.status not in {JournalStatus.POSTED, JournalStatus.REVERSED}:
            raise ValidationError("Only posted ledger lines can be reconciled.")
        if line.journal_entry.legal_entity_id != reconciliation.legal_entity_id:
            raise ValidationError("Journal line belongs to another legal entity.")
        if line.account_id != account.ledger_account_id:
            raise ValidationError("Journal line does not belong to the selected financial account.")
        if line.journal_entry.entry_date > reconciliation.end_date:
            raise ValidationError("Journal line is later than the reconciliation statement date.")
        if line.currency != account.currency:
            raise ValidationError("Journal line currency must match the financial account currency.")

    reconciliation.items.all().delete()
    for line in lines:
        ReconciliationItem.objects.create(reconciliation=reconciliation, journal_line=line)

    summary = reconciliation_summary(reconciliation)
    _audit(
        membership=membership,
        reconciliation=reconciliation,
        action="reconciliation.items_replaced",
        state={
            "selected_count": summary["selected_count"],
            "difference": str(summary["difference"]),
        },
        request=request,
    )
    return reconciliation


@transaction.atomic
def complete_reconciliation(
    *,
    membership: Membership,
    reconciliation: AccountReconciliation,
    request=None,
) -> AccountReconciliation:
    _require_permission(membership, Permission.MANAGE_RECONCILIATION)
    _require_entity_scope(membership, reconciliation.legal_entity)
    reconciliation = AccountReconciliation.objects.select_for_update().get(pk=reconciliation.pk)
    if reconciliation.status != ReconciliationStatus.DRAFT:
        raise ValidationError("Only draft reconciliations can be completed.")
    summary = reconciliation_summary(reconciliation)
    if summary["difference"] != Decimal("0"):
        raise ValidationError("Reconciliation difference must be zero before completion.")
    reconciliation.status = ReconciliationStatus.COMPLETED
    reconciliation.completed_by = membership.user
    reconciliation.completed_at = timezone.now()
    reconciliation.save(update_fields=["status", "completed_by", "completed_at", "updated_at"])
    _audit(
        membership=membership,
        reconciliation=reconciliation,
        action="reconciliation.completed",
        state={
            "statement_ending_balance": str(reconciliation.statement_ending_balance),
            "selected_count": summary["selected_count"],
            "difference": "0",
        },
        request=request,
    )
    return reconciliation
