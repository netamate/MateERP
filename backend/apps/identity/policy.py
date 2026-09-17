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
    VIEW_OPERATIONS = "VIEW_OPERATIONS"
    MANAGE_OPERATIONS = "MANAGE_OPERATIONS"
    VIEW_PLANNING = "VIEW_PLANNING"
    MANAGE_PLANNING = "MANAGE_PLANNING"


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
        Permission.VIEW_OPERATIONS,
        Permission.MANAGE_OPERATIONS,
        Permission.VIEW_PLANNING,
        Permission.MANAGE_PLANNING,
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
        }
    ),
}


def has_permission(membership: Membership | None, permission: Permission) -> bool:
    if not membership or membership.status != MembershipStatus.ACTIVE:
        return False
    return permission in ROLE_PERMISSIONS.get(membership.role, frozenset())
