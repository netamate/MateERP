from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.finance.models import Expense, ExpenseStatus, Reimbursement, ReimbursementStatus
from apps.identity.models import LegalEntity, Membership, MembershipStatus
from apps.identity.policy import Permission, has_permission
from apps.operations.selectors import renewal_calendar

from ...models import Notification, NotificationKind, NotificationSeverity
from ...services import resolve_notifications, upsert_notification


class Command(BaseCommand):
    help = "Refresh idempotent MateERP renewal and approval notifications."

    def add_arguments(self, parser):
        parser.add_argument(
            "--horizon-days",
            type=int,
            default=30,
            help="Create renewal alerts for obligations due within this many days.",
        )

    def handle(self, *args, **options):
        horizon_days = options["horizon_days"]
        if horizon_days < 1:
            raise ValueError("--horizon-days must be at least 1.")
        today = timezone.localdate()
        end_date = today + timedelta(days=horizon_days)
        created_or_updated = 0
        resolved = 0

        for entity in LegalEntity.objects.filter(status="ACTIVE").select_related("organization"):
            memberships = list(
                Membership.objects.filter(
                    organization=entity.organization,
                    status=MembershipStatus.ACTIVE,
                ).select_related("user")
            )
            viewers = [
                membership
                for membership in memberships
                if has_permission(membership, Permission.VIEW_NOTIFICATIONS)
                and self._can_access_entity(membership, entity)
            ]
            approvers = [
                membership
                for membership in viewers
                if has_permission(membership, Permission.APPROVE_FINANCE)
            ]
            active_keys: dict[str, set[str]] = {
                str(membership.user_id): set() for membership in viewers
            }

            for renewal in renewal_calendar(entity, start_date=today, end_date=end_date):
                key = (
                    f"renewal:{entity.id}:{renewal['source_type']}:"
                    f"{renewal['source_id']}:{renewal['renewal_date']}"
                )
                days_remaining = (renewal["renewal_date"] - today).days
                severity = (
                    NotificationSeverity.CRITICAL
                    if days_remaining <= 7
                    else NotificationSeverity.WARNING
                )
                link = {
                    "SUBSCRIPTION": "/operations/subscriptions",
                    "DOMAIN": "/operations/domains",
                    "INFRASTRUCTURE": "/operations/infrastructure",
                }[renewal["source_type"]]
                for membership in viewers:
                    upsert_notification(
                        organization=entity.organization,
                        legal_entity=entity,
                        recipient=membership.user,
                        dedupe_key=key,
                        kind=NotificationKind.RENEWAL_DUE,
                        severity=severity,
                        title=f"Renewal due: {renewal['name']}",
                        message=(
                            f"{renewal['source_type'].title()} renews on "
                            f"{renewal['renewal_date']} for {renewal['amount']} "
                            f"{renewal['currency']}."
                        ),
                        link=link,
                        due_date=renewal["renewal_date"],
                    )
                    active_keys[str(membership.user_id)].add(key)
                    created_or_updated += 1

            submitted_expenses = Expense.objects.filter(
                legal_entity=entity,
                status=ExpenseStatus.SUBMITTED,
            )
            for expense in submitted_expenses:
                key = f"approval:expense:{entity.id}:{expense.id}"
                for membership in approvers:
                    upsert_notification(
                        organization=entity.organization,
                        legal_entity=entity,
                        recipient=membership.user,
                        dedupe_key=key,
                        kind=NotificationKind.EXPENSE_APPROVAL,
                        severity=NotificationSeverity.WARNING,
                        title="Expense waiting for approval",
                        message=f"{expense.description}: {expense.amount} {expense.currency}",
                        link="/expenses",
                    )
                    active_keys[str(membership.user_id)].add(key)
                    created_or_updated += 1

            submitted_reimbursements = Reimbursement.objects.filter(
                legal_entity=entity,
                status=ReimbursementStatus.SUBMITTED,
            )
            for reimbursement in submitted_reimbursements:
                key = f"approval:reimbursement:{entity.id}:{reimbursement.id}"
                for membership in approvers:
                    upsert_notification(
                        organization=entity.organization,
                        legal_entity=entity,
                        recipient=membership.user,
                        dedupe_key=key,
                        kind=NotificationKind.REIMBURSEMENT_APPROVAL,
                        severity=NotificationSeverity.WARNING,
                        title="Reimbursement waiting for approval",
                        message=(
                            f"{reimbursement.description}: {reimbursement.amount} "
                            f"{reimbursement.currency}"
                        ),
                        link="/reimbursements",
                    )
                    active_keys[str(membership.user_id)].add(key)
                    created_or_updated += 1

            for membership in viewers:
                generated = Notification.objects.filter(
                    organization=entity.organization,
                    legal_entity=entity,
                    recipient=membership.user,
                    kind__in=[
                        NotificationKind.RENEWAL_DUE,
                        NotificationKind.EXPENSE_APPROVAL,
                        NotificationKind.REIMBURSEMENT_APPROVAL,
                    ],
                    resolved_at__isnull=True,
                )
                keys = active_keys[str(membership.user_id)]
                if keys:
                    generated = generated.exclude(dedupe_key__in=keys)
                resolved += resolve_notifications(generated)

        self.stdout.write(
            self.style.SUCCESS(
                f"Notifications refreshed: {created_or_updated} active, {resolved} resolved."
            )
        )

    @staticmethod
    def _can_access_entity(membership, entity):
        if membership.all_legal_entities:
            return True
        return membership.legal_entities.filter(id=entity.id).exists()
