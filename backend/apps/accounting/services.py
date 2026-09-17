from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit.services import record_audit_event
from apps.identity.models import Membership
from apps.identity.policy import Permission, has_permission

from .models import (
    Account,
    FiscalPeriod,
    JournalEntry,
    JournalLine,
    JournalSequence,
    JournalStatus,
    PeriodStatus,
)


def _require_permission(membership: Membership, permission: Permission) -> None:
    if not has_permission(membership, permission):
        raise PermissionDenied("You do not have permission for this accounting action.")


def _require_same_entity(membership: Membership, legal_entity_id) -> None:
    if membership.organization_id != membership.organization_id:
        raise PermissionDenied("Cross-organization accounting access is not allowed.")
    if not membership.all_legal_entities:
        allowed = membership.legal_entities.filter(id=legal_entity_id).exists()
        if not allowed:
            raise PermissionDenied("You do not have access to this legal entity.")


def _require_open_period(legal_entity, entry_date: date) -> FiscalPeriod:
    period = FiscalPeriod.objects.filter(
        legal_entity=legal_entity,
        start_date__lte=entry_date,
        end_date__gte=entry_date,
    ).first()
    if period is None:
        raise ValidationError("No fiscal period exists for the journal date.")
    if period.status != PeriodStatus.OPEN:
        raise ValidationError("The fiscal period is closed for posting.")
    return period


def _next_journal_number(legal_entity) -> str:
    sequence, _ = JournalSequence.objects.select_for_update().get_or_create(
        legal_entity=legal_entity
    )
    number = sequence.next_number
    sequence.next_number += 1
    sequence.save(update_fields=["next_number"])
    return f"JE-{number:08d}"


@transaction.atomic
def create_journal(
    *,
    membership: Membership,
    legal_entity,
    entry_date: date,
    memo: str,
    lines: list[dict],
    source_type: str = "MANUAL",
    source_id: str = "",
    request=None,
) -> JournalEntry:
    _require_permission(membership, Permission.POST_JOURNAL)
    _require_same_entity(membership, legal_entity.id)
    if legal_entity.organization_id != membership.organization_id:
        raise PermissionDenied("Legal entity does not belong to the active organization.")
    _require_open_period(legal_entity, entry_date)
    if len(lines) < 2:
        raise ValidationError("A journal entry requires at least two lines.")

    journal = JournalEntry.objects.create(
        legal_entity=legal_entity,
        number=_next_journal_number(legal_entity),
        entry_date=entry_date,
        memo=memo,
        source_type=source_type,
        source_id=source_id,
        created_by=membership.user,
    )

    account_ids = {line["account_id"] for line in lines}
    accounts = {
        str(account.id): account
        for account in Account.objects.filter(
            legal_entity=legal_entity,
            id__in=account_ids,
            is_active=True,
        )
    }
    if len(accounts) != len({str(value) for value in account_ids}):
        raise ValidationError("One or more accounts are invalid for this legal entity.")

    for line in lines:
        JournalLine.objects.create(
            journal_entry=journal,
            account=accounts[str(line["account_id"])],
            description=line.get("description", ""),
            debit=line.get("debit", Decimal("0")),
            credit=line.get("credit", Decimal("0")),
            currency=line.get("currency", legal_entity.base_currency),
            fx_rate=line.get("fx_rate", Decimal("1")),
            tax_code_id=line.get("tax_code_id"),
        )

    _validate_balanced(journal)
    record_audit_event(
        actor=membership.user,
        organization=membership.organization,
        legal_entity=legal_entity,
        action="accounting.journal_created",
        object_type="JournalEntry",
        object_id=journal.id,
        new_state={"number": journal.number, "entry_date": str(entry_date)},
        request=request,
    )
    return journal


def _validate_balanced(journal: JournalEntry) -> None:
    totals = journal.lines.aggregate(
        debit=Sum("base_debit"),
        credit=Sum("base_credit"),
    )
    debit = totals["debit"] or Decimal("0")
    credit = totals["credit"] or Decimal("0")
    if debit != credit:
        raise ValidationError("Journal entry debits and credits must balance in base currency.")
    if debit <= 0:
        raise ValidationError("Journal entry total must be greater than zero.")


@transaction.atomic
def post_journal(*, membership: Membership, journal: JournalEntry, request=None) -> JournalEntry:
    _require_permission(membership, Permission.POST_JOURNAL)
    if journal.legal_entity.organization_id != membership.organization_id:
        raise PermissionDenied("Cross-organization posting is not allowed.")
    _require_same_entity(membership, journal.legal_entity_id)
    if journal.status != JournalStatus.DRAFT:
        raise ValidationError("Only draft journals can be posted.")
    _require_open_period(journal.legal_entity, journal.entry_date)
    _validate_balanced(journal)

    journal.status = JournalStatus.POSTED
    journal.posted_by = membership.user
    journal.posted_at = timezone.now()
    journal.save(update_fields=["status", "posted_by", "posted_at", "updated_at"])
    record_audit_event(
        actor=membership.user,
        organization=membership.organization,
        legal_entity=journal.legal_entity,
        action="accounting.journal_posted",
        object_type="JournalEntry",
        object_id=journal.id,
        new_state={"number": journal.number, "status": journal.status},
        request=request,
    )
    return journal


@transaction.atomic
def reverse_journal(
    *,
    membership: Membership,
    journal: JournalEntry,
    reversal_date: date,
    memo: str = "",
    request=None,
) -> JournalEntry:
    _require_permission(membership, Permission.REVERSE_JOURNAL)
    if journal.legal_entity.organization_id != membership.organization_id:
        raise PermissionDenied("Cross-organization reversal is not allowed.")
    _require_same_entity(membership, journal.legal_entity_id)
    if journal.status != JournalStatus.POSTED:
        raise ValidationError("Only posted journals can be reversed.")
    if hasattr(journal, "reversal_entry"):
        raise ValidationError("This journal has already been reversed.")
    _require_open_period(journal.legal_entity, reversal_date)

    reversal = JournalEntry.objects.create(
        legal_entity=journal.legal_entity,
        number=_next_journal_number(journal.legal_entity),
        entry_date=reversal_date,
        memo=memo or f"Reversal of {journal.number}",
        source_type="REVERSAL",
        source_id=str(journal.id),
        reversal_of=journal,
        created_by=membership.user,
    )
    for line in journal.lines.select_related("account", "tax_code"):
        JournalLine.objects.create(
            journal_entry=reversal,
            account=line.account,
            description=line.description,
            debit=line.credit,
            credit=line.debit,
            currency=line.currency,
            fx_rate=line.fx_rate,
            tax_code=line.tax_code,
        )
    post_journal(membership=membership, journal=reversal, request=request)
    journal.status = JournalStatus.REVERSED
    journal.save(update_fields=["status", "updated_at"])
    record_audit_event(
        actor=membership.user,
        organization=membership.organization,
        legal_entity=journal.legal_entity,
        action="accounting.journal_reversed",
        object_type="JournalEntry",
        object_id=journal.id,
        new_state={"reversal_id": str(reversal.id)},
        request=request,
    )
    return reversal


@transaction.atomic
def close_period(
    *,
    membership: Membership,
    period: FiscalPeriod,
    hard_close: bool,
    request=None,
) -> FiscalPeriod:
    _require_permission(membership, Permission.CLOSE_PERIOD)
    if period.legal_entity.organization_id != membership.organization_id:
        raise PermissionDenied("Cross-organization period close is not allowed.")
    _require_same_entity(membership, period.legal_entity_id)
    period.status = PeriodStatus.HARD_CLOSED if hard_close else PeriodStatus.SOFT_CLOSED
    period.closed_by = membership.user
    period.closed_at = timezone.now()
    period.save(update_fields=["status", "closed_by", "closed_at", "updated_at"])
    record_audit_event(
        actor=membership.user,
        organization=membership.organization,
        legal_entity=period.legal_entity,
        action="accounting.period_closed",
        object_type="FiscalPeriod",
        object_id=period.id,
        new_state={"status": period.status},
        request=request,
    )
    return period
