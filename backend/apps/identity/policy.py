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
        }
    ),
    Role.MEMBER: frozenset(
        {
            Permission.VIEW_ORGANIZATION,
            Permission.VIEW_MEMBERS,
            Permission.VIEW_LEGAL_ENTITY,
            Permission.VIEW_ACCOUNTING,
        }
    ),
    Role.VIEWER: frozenset(
        {
            Permission.VIEW_ORGANIZATION,
            Permission.VIEW_MEMBERS,
            Permission.VIEW_LEGAL_ENTITY,
            Permission.VIEW_ACCOUNTING,
        }
    ),
}


def has_permission(membership: Membership | None, permission: Permission) -> bool:
    if not membership or membership.status != MembershipStatus.ACTIVE:
        return False
    return permission in ROLE_PERMISSIONS.get(membership.role, frozenset())
