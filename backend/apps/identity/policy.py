from enum import StrEnum

from .models import Membership, MembershipStatus, Role


class Permission(StrEnum):
    VIEW_ORGANIZATION = "VIEW_ORGANIZATION"
    MANAGE_ORGANIZATION = "MANAGE_ORGANIZATION"
    VIEW_MEMBERS = "VIEW_MEMBERS"
    MANAGE_MEMBERS = "MANAGE_MEMBERS"
    VIEW_LEGAL_ENTITY = "VIEW_LEGAL_ENTITY"
    MANAGE_LEGAL_ENTITY = "MANAGE_LEGAL_ENTITY"
    VIEW_ACCOUNTING = "VIEW_ACCOUNTING"
    POST_JOURNAL = "POST_JOURNAL"
    REVERSE_JOURNAL = "REVERSE_JOURNAL"
    CLOSE_PERIOD = "CLOSE_PERIOD"
    ACCOUNT_ADJUSTMENT = "ACCOUNT_ADJUSTMENT"
    CHANGE_BASE_CURRENCY = "CHANGE_BASE_CURRENCY"
    EDIT_CHART_OF_ACCOUNTS = "EDIT_CHART_OF_ACCOUNTS"
    MANAGE_TAX_CONFIG = "MANAGE_TAX_CONFIG"
    MANAGE_FX_RATES = "MANAGE_FX_RATES"
    VIEW_FINANCE = "VIEW_FINANCE"
    MANAGE_FINANCE = "MANAGE_FINANCE"
    SUBMIT_FINANCE = "SUBMIT_FINANCE"
    APPROVE_FINANCE = "APPROVE_FINANCE"
    PAY_FINANCE = "PAY_FINANCE"
    MANAGE_FINANCE_DOCUMENTS = "MANAGE_FINANCE_DOCUMENTS"
    VIEW_SENSITIVE_FINANCE_DOCUMENTS = "VIEW_SENSITIVE_FINANCE_DOCUMENTS"
    VIEW_OPERATIONS = "VIEW_OPERATIONS"
    MANAGE_OPERATIONS = "MANAGE_OPERATIONS"
    VIEW_PLANNING = "VIEW_PLANNING"
    MANAGE_PLANNING = "MANAGE_PLANNING"
    VIEW_REPORTS = "VIEW_REPORTS"
    VIEW_AUDIT_LOG = "VIEW_AUDIT_LOG"
    VIEW_NOTIFICATIONS = "VIEW_NOTIFICATIONS"
    MANAGE_NOTIFICATIONS = "MANAGE_NOTIFICATIONS"
    VIEW_AUTOMATION = "VIEW_AUTOMATION"
    MANAGE_AUTOMATION = "MANAGE_AUTOMATION"
    VIEW_RECONCILIATION = "VIEW_RECONCILIATION"
    MANAGE_RECONCILIATION = "MANAGE_RECONCILIATION"


FINANCE_PERMISSIONS = frozenset(
    {
        Permission.VIEW_ORGANIZATION,
        Permission.VIEW_MEMBERS,
        Permission.VIEW_LEGAL_ENTITY,
        Permission.VIEW_ACCOUNTING,
        Permission.POST_JOURNAL,
        Permission.REVERSE_JOURNAL,
        Permission.CLOSE_PERIOD,
        Permission.ACCOUNT_ADJUSTMENT,
        Permission.EDIT_CHART_OF_ACCOUNTS,
        Permission.MANAGE_TAX_CONFIG,
        Permission.MANAGE_FX_RATES,
        Permission.VIEW_FINANCE,
        Permission.MANAGE_FINANCE,
        Permission.SUBMIT_FINANCE,
        Permission.APPROVE_FINANCE,
        Permission.PAY_FINANCE,
        Permission.MANAGE_FINANCE_DOCUMENTS,
        Permission.VIEW_SENSITIVE_FINANCE_DOCUMENTS,
        Permission.VIEW_OPERATIONS,
        Permission.MANAGE_OPERATIONS,
        Permission.VIEW_PLANNING,
        Permission.MANAGE_PLANNING,
        Permission.VIEW_REPORTS,
        Permission.VIEW_AUDIT_LOG,
        Permission.VIEW_NOTIFICATIONS,
        Permission.MANAGE_NOTIFICATIONS,
        Permission.VIEW_AUTOMATION,
        Permission.MANAGE_AUTOMATION,
        Permission.VIEW_RECONCILIATION,
        Permission.MANAGE_RECONCILIATION,
    }
)

ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.ADMINISTRATOR: frozenset(Permission),
    Role.FINANCE_MANAGER: FINANCE_PERMISSIONS,
    Role.APPROVER: frozenset(
        {
            Permission.VIEW_ORGANIZATION,
            Permission.VIEW_MEMBERS,
            Permission.VIEW_LEGAL_ENTITY,
            Permission.VIEW_ACCOUNTING,
            Permission.POST_JOURNAL,
            Permission.VIEW_FINANCE,
            Permission.APPROVE_FINANCE,
            Permission.VIEW_OPERATIONS,
            Permission.VIEW_PLANNING,
            Permission.VIEW_REPORTS,
            Permission.VIEW_NOTIFICATIONS,
            Permission.VIEW_AUTOMATION,
        }
    ),
    Role.MEMBER: frozenset(
        {
            Permission.VIEW_ORGANIZATION,
            Permission.VIEW_MEMBERS,
            Permission.VIEW_LEGAL_ENTITY,
            Permission.VIEW_ACCOUNTING,
            Permission.VIEW_FINANCE,
            Permission.SUBMIT_FINANCE,
            Permission.MANAGE_FINANCE_DOCUMENTS,
            Permission.VIEW_OPERATIONS,
            Permission.VIEW_PLANNING,
            Permission.VIEW_REPORTS,
            Permission.VIEW_NOTIFICATIONS,
            Permission.VIEW_AUTOMATION,
        }
    ),
    Role.VIEWER: frozenset(
        {
            Permission.VIEW_ORGANIZATION,
            Permission.VIEW_MEMBERS,
            Permission.VIEW_LEGAL_ENTITY,
            Permission.VIEW_ACCOUNTING,
            Permission.VIEW_FINANCE,
            Permission.VIEW_OPERATIONS,
            Permission.VIEW_PLANNING,
            Permission.VIEW_REPORTS,
            Permission.VIEW_NOTIFICATIONS,
            Permission.VIEW_AUTOMATION,
            Permission.VIEW_RECONCILIATION,
        }
    ),
}


def has_permission(membership: Membership | None, permission: Permission) -> bool:
    if not membership or membership.status != MembershipStatus.ACTIVE:
        return False
    return permission in ROLE_PERMISSIONS.get(membership.role, frozenset())
