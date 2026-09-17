from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounting.services import create_journal, post_journal
from apps.audit.services import record_audit_event
from apps.identity.models import Membership, MembershipStatus
from apps.identity.policy import Permission, has_permission

from .models import (
    ApprovalAction,
    ApprovalActionType,
    ApprovalObjectType,
    Expense,
    ExpensePayment,
    ExpenseStatus,
    FinancialAccount,
    FounderFunding,
    Income,
    RecordStatus,
    Reimbursement,
    ReimbursementPayment,
    ReimbursementStatus,
    Transfer,
)


def _require_permission(membership: Membership, permission: Permission) -> None:
    if not has_permission(membership, permission):
        raise PermissionDenied("You do not have permission for this finance action.")


def _require_entity_scope(membership: Membership, legal_entity) -> None:
    if legal_entity.organization_id != membership.organization_id:
        raise PermissionDenied("Cross-organization finance access is not allowed.")
    if membership.all_legal_entities:
        return
    if not membership.legal_entities.filter(id=legal_entity.id).exists():
        raise PermissionDenied("You do not have access to this legal entity.")


def _base_amount(amount: Decimal, fx_rate: Decimal) -> Decimal:
    return (amount * fx_rate).quantize(Decimal("0.01"))


def _audit(*, membership, legal_entity, action, object_type, object_id, state, request=None):
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


def _record_approval(*, record, membership, object_type, action, comment=""):
    ApprovalAction.objects.create(
        legal_entity=record.legal_entity,
        object_type=object_type,
        object_id=record.id,
        action=action,
        actor=membership.user,
        comment=comment,
    )


@transaction.atomic
def create_expense(*, membership: Membership, legal_entity, request=None, **data) -> Expense:
    _require_permission(membership, Permission.SUBMIT_FINANCE)
    _require_entity_scope(membership, legal_entity)
    expense = Expense.objects.create(
        legal_entity=legal_entity,
        created_by=membership.user,
        **data,
    )
    _audit(
        membership=membership,
        legal_entity=legal_entity,
        action="finance.expense_created",
        object_type="Expense",
        object_id=expense.id,
        state={"amount": str(expense.amount), "currency": expense.currency},
        request=request,
    )
    return expense


@transaction.atomic
def submit_expense(
    *,
    membership: Membership,
    expense: Expense,
    comment: str = "",
    request=None,
) -> Expense:
    _require_permission(membership, Permission.SUBMIT_FINANCE)
    _require_entity_scope(membership, expense.legal_entity)
    if expense.status != ExpenseStatus.DRAFT:
        raise ValidationError("Only draft expenses can be submitted.")
    expense.status = ExpenseStatus.SUBMITTED
    expense.save(update_fields=["status", "updated_at"])
    _record_approval(
        record=expense,
        membership=membership,
        object_type=ApprovalObjectType.EXPENSE,
        action=ApprovalActionType.SUBMITTED,
        comment=comment,
    )
    _audit(
        membership=membership,
        legal_entity=expense.legal_entity,
        action="finance.expense_submitted",
        object_type="Expense",
        object_id=expense.id,
        state={"status": expense.status},
        request=request,
    )
    return expense


@transaction.atomic
def approve_expense(
    *,
    membership: Membership,
    expense: Expense,
    comment: str = "",
    request=None,
) -> Expense:
    _require_permission(membership, Permission.APPROVE_FINANCE)
    _require_entity_scope(membership, expense.legal_entity)
    if expense.status != ExpenseStatus.SUBMITTED:
        raise ValidationError("Only submitted expenses can be approved.")

    net_amount = expense.amount - expense.tax_amount
    lines = [
        {
            "account_id": expense.expense_account_id,
            "description": expense.description,
            "debit": net_amount,
            "credit": Decimal("0"),
            "currency": expense.currency,
            "fx_rate": expense.fx_rate,
        }
    ]
    if expense.tax_amount > 0:
        lines.append(
            {
                "account_id": expense.tax_code.input_account_id,
                "description": f"Tax: {expense.description}",
                "debit": expense.tax_amount,
                "credit": Decimal("0"),
                "currency": expense.currency,
                "fx_rate": expense.fx_rate,
                "tax_code_id": expense.tax_code_id,
            }
        )
    lines.append(
        {
            "account_id": expense.payable_account_id,
            "description": expense.description,
            "debit": Decimal("0"),
            "credit": expense.amount,
            "currency": expense.currency,
            "fx_rate": expense.fx_rate,
        }
    )
    journal = create_journal(
        membership=membership,
        legal_entity=expense.legal_entity,
        entry_date=expense.expense_date,
        memo=f"Expense: {expense.description}",
        lines=lines,
        source_type="EXPENSE",
        source_id=str(expense.id),
        request=request,
    )
    post_journal(membership=membership, journal=journal, request=request)

    expense.status = ExpenseStatus.APPROVED
    expense.journal_entry = journal
    expense.approved_by = membership.user
    expense.approved_at = timezone.now()
    expense.rejected_by = None
    expense.rejected_at = None
    expense.rejection_reason = ""
    expense.save(
        update_fields=[
            "status",
            "journal_entry",
            "approved_by",
            "approved_at",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "updated_at",
        ]
    )
    _record_approval(
        record=expense,
        membership=membership,
        object_type=ApprovalObjectType.EXPENSE,
        action=ApprovalActionType.APPROVED,
        comment=comment,
    )
    _audit(
        membership=membership,
        legal_entity=expense.legal_entity,
        action="finance.expense_approved",
        object_type="Expense",
        object_id=expense.id,
        state={"status": expense.status, "journal_id": str(journal.id)},
        request=request,
    )
    return expense


@transaction.atomic
def reject_expense(
    *,
    membership: Membership,
    expense: Expense,
    reason: str,
    request=None,
) -> Expense:
    _require_permission(membership, Permission.APPROVE_FINANCE)
    _require_entity_scope(membership, expense.legal_entity)
    if expense.status != ExpenseStatus.SUBMITTED:
        raise ValidationError("Only submitted expenses can be rejected.")
    expense.status = ExpenseStatus.REJECTED
    expense.rejected_by = membership.user
    expense.rejected_at = timezone.now()
    expense.rejection_reason = reason
    expense.save(
        update_fields=[
            "status",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "updated_at",
        ]
    )
    _record_approval(
        record=expense,
        membership=membership,
        object_type=ApprovalObjectType.EXPENSE,
        action=ApprovalActionType.REJECTED,
        comment=reason,
    )
    _audit(
        membership=membership,
        legal_entity=expense.legal_entity,
        action="finance.expense_rejected",
        object_type="Expense",
        object_id=expense.id,
        state={"status": expense.status, "reason": reason},
        request=request,
    )
    return expense


@transaction.atomic
def pay_expense(
    *,
    membership: Membership,
    expense: Expense,
    financial_account: FinancialAccount,
    payment_date,
    amount: Decimal,
    currency: str,
    fx_rate: Decimal,
    reference: str = "",
    request=None,
) -> ExpensePayment:
    _require_permission(membership, Permission.PAY_FINANCE)
    _require_entity_scope(membership, expense.legal_entity)
    if expense.status not in {ExpenseStatus.APPROVED, ExpenseStatus.PARTIALLY_PAID}:
        raise ValidationError("Only approved expenses can be paid.")
    if financial_account.legal_entity_id != expense.legal_entity_id:
        raise ValidationError("Financial account must belong to the expense legal entity.")

    payment_base = _base_amount(amount, fx_rate)
    total_base = _base_amount(expense.amount, expense.fx_rate)
    paid_base = expense.payments.aggregate(total=Sum("base_amount"))["total"] or Decimal("0")
    if payment_base <= 0 or paid_base + payment_base > total_base:
        raise ValidationError("Payment exceeds the outstanding expense balance.")

    journal = create_journal(
        membership=membership,
        legal_entity=expense.legal_entity,
        entry_date=payment_date,
        memo=f"Expense payment: {expense.description}",
        source_type="EXPENSE_PAYMENT",
        source_id=str(expense.id),
        request=request,
        lines=[
            {
                "account_id": expense.payable_account_id,
                "description": expense.description,
                "debit": payment_base,
                "credit": Decimal("0"),
                "currency": expense.legal_entity.base_currency,
                "fx_rate": Decimal("1"),
            },
            {
                "account_id": financial_account.ledger_account_id,
                "description": expense.description,
                "debit": Decimal("0"),
                "credit": amount,
                "currency": currency,
                "fx_rate": fx_rate,
            },
        ],
    )
    post_journal(membership=membership, journal=journal, request=request)
    payment = ExpensePayment.objects.create(
        legal_entity=expense.legal_entity,
        expense=expense,
        financial_account=financial_account,
        payment_date=payment_date,
        amount=amount,
        currency=currency,
        fx_rate=fx_rate,
        reference=reference,
        journal_entry=journal,
        created_by=membership.user,
    )
    expense.status = (
        ExpenseStatus.PAID
        if paid_base + payment.base_amount == total_base
        else ExpenseStatus.PARTIALLY_PAID
    )
    expense.save(update_fields=["status", "updated_at"])
    _audit(
        membership=membership,
        legal_entity=expense.legal_entity,
        action="finance.expense_paid",
        object_type="ExpensePayment",
        object_id=payment.id,
        state={"amount": str(payment.amount), "status": expense.status},
        request=request,
    )
    return payment


@transaction.atomic
def record_income(*, membership: Membership, legal_entity, request=None, **data) -> Income:
    _require_permission(membership, Permission.MANAGE_FINANCE)
    _require_entity_scope(membership, legal_entity)
    income = Income.objects.create(
        legal_entity=legal_entity,
        created_by=membership.user,
        **data,
    )
    journal = create_journal(
        membership=membership,
        legal_entity=legal_entity,
        entry_date=income.income_date,
        memo=f"Income: {income.description}",
        source_type="INCOME",
        source_id=str(income.id),
        request=request,
        lines=[
            {
                "account_id": income.financial_account.ledger_account_id,
                "description": income.description,
                "debit": income.amount,
                "credit": Decimal("0"),
                "currency": income.currency,
                "fx_rate": income.fx_rate,
            },
            {
                "account_id": income.revenue_account_id,
                "description": income.description,
                "debit": Decimal("0"),
                "credit": income.amount,
                "currency": income.currency,
                "fx_rate": income.fx_rate,
            },
        ],
    )
    post_journal(membership=membership, journal=journal, request=request)
    income.status = RecordStatus.POSTED
    income.journal_entry = journal
    income.save(update_fields=["status", "journal_entry"])
    _audit(
        membership=membership,
        legal_entity=legal_entity,
        action="finance.income_recorded",
        object_type="Income",
        object_id=income.id,
        state={"amount": str(income.amount), "journal_id": str(journal.id)},
        request=request,
    )
    return income


@transaction.atomic
def record_transfer(*, membership: Membership, legal_entity, request=None, **data) -> Transfer:
    _require_permission(membership, Permission.MANAGE_FINANCE)
    _require_entity_scope(membership, legal_entity)
    transfer = Transfer.objects.create(
        legal_entity=legal_entity,
        created_by=membership.user,
        **data,
    )
    journal = create_journal(
        membership=membership,
        legal_entity=legal_entity,
        entry_date=transfer.transfer_date,
        memo=transfer.memo or "Financial account transfer",
        source_type="TRANSFER",
        source_id=str(transfer.id),
        request=request,
        lines=[
            {
                "account_id": transfer.to_account.ledger_account_id,
                "description": transfer.memo,
                "debit": transfer.destination_amount,
                "credit": Decimal("0"),
                "currency": transfer.to_account.currency,
                "fx_rate": transfer.destination_fx_rate,
            },
            {
                "account_id": transfer.from_account.ledger_account_id,
                "description": transfer.memo,
                "debit": Decimal("0"),
                "credit": transfer.source_amount,
                "currency": transfer.from_account.currency,
                "fx_rate": transfer.source_fx_rate,
            },
        ],
    )
    post_journal(membership=membership, journal=journal, request=request)
    transfer.status = RecordStatus.POSTED
    transfer.journal_entry = journal
    transfer.save(update_fields=["status", "journal_entry"])
    _audit(
        membership=membership,
        legal_entity=legal_entity,
        action="finance.transfer_recorded",
        object_type="Transfer",
        object_id=transfer.id,
        state={"journal_id": str(journal.id)},
        request=request,
    )
    return transfer


@transaction.atomic
def record_founder_funding(
    *,
    membership: Membership,
    legal_entity,
    request=None,
    **data,
) -> FounderFunding:
    _require_permission(membership, Permission.MANAGE_FINANCE)
    _require_entity_scope(membership, legal_entity)
    funding = FounderFunding.objects.create(
        legal_entity=legal_entity,
        created_by=membership.user,
        **data,
    )
    journal = create_journal(
        membership=membership,
        legal_entity=legal_entity,
        entry_date=funding.funding_date,
        memo=funding.memo or f"Founder {funding.funding_type.lower()}",
        source_type="FOUNDER_FUNDING",
        source_id=str(funding.id),
        request=request,
        lines=[
            {
                "account_id": funding.financial_account.ledger_account_id,
                "description": funding.memo,
                "debit": funding.amount,
                "credit": Decimal("0"),
                "currency": funding.currency,
                "fx_rate": funding.fx_rate,
            },
            {
                "account_id": funding.counter_account_id,
                "description": funding.memo,
                "debit": Decimal("0"),
                "credit": funding.amount,
                "currency": funding.currency,
                "fx_rate": funding.fx_rate,
            },
        ],
    )
    post_journal(membership=membership, journal=journal, request=request)
    funding.status = RecordStatus.POSTED
    funding.journal_entry = journal
    funding.save(update_fields=["status", "journal_entry"])
    _audit(
        membership=membership,
        legal_entity=legal_entity,
        action="finance.founder_funding_recorded",
        object_type="FounderFunding",
        object_id=funding.id,
        state={"type": funding.funding_type, "journal_id": str(journal.id)},
        request=request,
    )
    return funding


@transaction.atomic
def create_reimbursement(
    *,
    membership: Membership,
    legal_entity,
    request=None,
    **data,
) -> Reimbursement:
    _require_permission(membership, Permission.SUBMIT_FINANCE)
    _require_entity_scope(membership, legal_entity)
    claimant = data.get("claimant")
    if not Membership.objects.filter(
        organization=membership.organization,
        user=claimant,
        status=MembershipStatus.ACTIVE,
    ).exists():
        raise ValidationError("Claimant must be an active member of the organization.")
    reimbursement = Reimbursement.objects.create(
        legal_entity=legal_entity,
        created_by=membership.user,
        **data,
    )
    _audit(
        membership=membership,
        legal_entity=legal_entity,
        action="finance.reimbursement_created",
        object_type="Reimbursement",
        object_id=reimbursement.id,
        state={"amount": str(reimbursement.amount), "currency": reimbursement.currency},
        request=request,
    )
    return reimbursement


@transaction.atomic
def submit_reimbursement(
    *,
    membership: Membership,
    reimbursement: Reimbursement,
    comment: str = "",
    request=None,
) -> Reimbursement:
    _require_permission(membership, Permission.SUBMIT_FINANCE)
    _require_entity_scope(membership, reimbursement.legal_entity)
    if reimbursement.status != ReimbursementStatus.DRAFT:
        raise ValidationError("Only draft reimbursements can be submitted.")
    reimbursement.status = ReimbursementStatus.SUBMITTED
    reimbursement.save(update_fields=["status", "updated_at"])
    _record_approval(
        record=reimbursement,
        membership=membership,
        object_type=ApprovalObjectType.REIMBURSEMENT,
        action=ApprovalActionType.SUBMITTED,
        comment=comment,
    )
    return reimbursement


@transaction.atomic
def approve_reimbursement(
    *,
    membership: Membership,
    reimbursement: Reimbursement,
    comment: str = "",
    request=None,
) -> Reimbursement:
    _require_permission(membership, Permission.APPROVE_FINANCE)
    _require_entity_scope(membership, reimbursement.legal_entity)
    if reimbursement.status != ReimbursementStatus.SUBMITTED:
        raise ValidationError("Only submitted reimbursements can be approved.")
    journal = create_journal(
        membership=membership,
        legal_entity=reimbursement.legal_entity,
        entry_date=reimbursement.expense_date,
        memo=f"Reimbursement: {reimbursement.description}",
        source_type="REIMBURSEMENT",
        source_id=str(reimbursement.id),
        request=request,
        lines=[
            {
                "account_id": reimbursement.expense_account_id,
                "description": reimbursement.description,
                "debit": reimbursement.amount,
                "credit": Decimal("0"),
                "currency": reimbursement.currency,
                "fx_rate": reimbursement.fx_rate,
            },
            {
                "account_id": reimbursement.payable_account_id,
                "description": reimbursement.description,
                "debit": Decimal("0"),
                "credit": reimbursement.amount,
                "currency": reimbursement.currency,
                "fx_rate": reimbursement.fx_rate,
            },
        ],
    )
    post_journal(membership=membership, journal=journal, request=request)
    reimbursement.status = ReimbursementStatus.APPROVED
    reimbursement.journal_entry = journal
    reimbursement.approved_by = membership.user
    reimbursement.approved_at = timezone.now()
    reimbursement.save(
        update_fields=["status", "journal_entry", "approved_by", "approved_at", "updated_at"]
    )
    _record_approval(
        record=reimbursement,
        membership=membership,
        object_type=ApprovalObjectType.REIMBURSEMENT,
        action=ApprovalActionType.APPROVED,
        comment=comment,
    )
    _audit(
        membership=membership,
        legal_entity=reimbursement.legal_entity,
        action="finance.reimbursement_approved",
        object_type="Reimbursement",
        object_id=reimbursement.id,
        state={"journal_id": str(journal.id)},
        request=request,
    )
    return reimbursement


@transaction.atomic
def reject_reimbursement(
    *,
    membership: Membership,
    reimbursement: Reimbursement,
    reason: str,
    request=None,
) -> Reimbursement:
    _require_permission(membership, Permission.APPROVE_FINANCE)
    _require_entity_scope(membership, reimbursement.legal_entity)
    if reimbursement.status != ReimbursementStatus.SUBMITTED:
        raise ValidationError("Only submitted reimbursements can be rejected.")
    reimbursement.status = ReimbursementStatus.REJECTED
    reimbursement.rejected_by = membership.user
    reimbursement.rejected_at = timezone.now()
    reimbursement.rejection_reason = reason
    reimbursement.save(
        update_fields=[
            "status",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "updated_at",
        ]
    )
    _record_approval(
        record=reimbursement,
        membership=membership,
        object_type=ApprovalObjectType.REIMBURSEMENT,
        action=ApprovalActionType.REJECTED,
        comment=reason,
    )
    return reimbursement


@transaction.atomic
def pay_reimbursement(
    *,
    membership: Membership,
    reimbursement: Reimbursement,
    financial_account: FinancialAccount,
    payment_date,
    amount: Decimal,
    currency: str,
    fx_rate: Decimal,
    reference: str = "",
    request=None,
) -> ReimbursementPayment:
    _require_permission(membership, Permission.PAY_FINANCE)
    _require_entity_scope(membership, reimbursement.legal_entity)
    if reimbursement.status not in {
        ReimbursementStatus.APPROVED,
        ReimbursementStatus.PARTIALLY_PAID,
    }:
        raise ValidationError("Only approved reimbursements can be paid.")
    if financial_account.legal_entity_id != reimbursement.legal_entity_id:
        raise ValidationError("Financial account must belong to the reimbursement legal entity.")

    payment_base = _base_amount(amount, fx_rate)
    total_base = _base_amount(reimbursement.amount, reimbursement.fx_rate)
    paid_base = reimbursement.payments.aggregate(total=Sum("base_amount"))["total"] or Decimal("0")
    if payment_base <= 0 or paid_base + payment_base > total_base:
        raise ValidationError("Payment exceeds the outstanding reimbursement balance.")

    journal = create_journal(
        membership=membership,
        legal_entity=reimbursement.legal_entity,
        entry_date=payment_date,
        memo=f"Reimbursement payment: {reimbursement.description}",
        source_type="REIMBURSEMENT_PAYMENT",
        source_id=str(reimbursement.id),
        request=request,
        lines=[
            {
                "account_id": reimbursement.payable_account_id,
                "description": reimbursement.description,
                "debit": payment_base,
                "credit": Decimal("0"),
                "currency": reimbursement.legal_entity.base_currency,
                "fx_rate": Decimal("1"),
            },
            {
                "account_id": financial_account.ledger_account_id,
                "description": reimbursement.description,
                "debit": Decimal("0"),
                "credit": amount,
                "currency": currency,
                "fx_rate": fx_rate,
            },
        ],
    )
    post_journal(membership=membership, journal=journal, request=request)
    payment = ReimbursementPayment.objects.create(
        legal_entity=reimbursement.legal_entity,
        reimbursement=reimbursement,
        financial_account=financial_account,
        payment_date=payment_date,
        amount=amount,
        currency=currency,
        fx_rate=fx_rate,
        reference=reference,
        journal_entry=journal,
        created_by=membership.user,
    )
    reimbursement.status = (
        ReimbursementStatus.PAID
        if paid_base + payment.base_amount == total_base
        else ReimbursementStatus.PARTIALLY_PAID
    )
    reimbursement.save(update_fields=["status", "updated_at"])
    _audit(
        membership=membership,
        legal_entity=reimbursement.legal_entity,
        action="finance.reimbursement_paid",
        object_type="ReimbursementPayment",
        object_id=payment.id,
        state={"amount": str(payment.amount), "status": reimbursement.status},
        request=request,
    )
    return payment
