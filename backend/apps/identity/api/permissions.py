from rest_framework.permissions import BasePermission

from apps.identity.policy import Permission, has_permission
from apps.identity.selectors import membership_for_user


class OrganizationPermission(BasePermission):
    required_permission: Permission = Permission.VIEW_ORGANIZATION

    def has_permission(self, request, view):
        organization_id = request.session.get("active_organization_id")
        if not organization_id:
            return False
        membership = membership_for_user(request.user, organization_id)
        request.membership = membership
        return has_permission(membership, self.required_permission)
