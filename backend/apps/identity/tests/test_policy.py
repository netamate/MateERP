import pytest
from django.core.exceptions import PermissionDenied

from apps.identity.models import Membership, Organization, Role, User
from apps.identity.policy import Permission, has_permission
from apps.identity.services import change_membership_role


@pytest.mark.django_db
def test_finance_manager_has_financial_permissions_but_not_member_management():
    user = User.objects.create_user(email="finance@example.com", password="safe-test-password")
    organization = Organization.objects.create(name="Example", slug="example")
    membership = Membership.objects.create(
        organization=organization,
        user=user,
        role=Role.FINANCE_MANAGER,
        all_legal_entities=True,
    )

    assert has_permission(membership, Permission.POST_JOURNAL)
    assert not has_permission(membership, Permission.MANAGE_MEMBERS)


@pytest.mark.django_db
def test_owner_has_all_declared_permissions():
    user = User.objects.create_user(email="owner@example.com", password="safe-test-password")
    organization = Organization.objects.create(name="Example", slug="example")
    membership = Membership.objects.create(
        organization=organization,
        user=user,
        role=Role.OWNER,
        all_legal_entities=True,
    )

    assert all(has_permission(membership, permission) for permission in Permission)


@pytest.mark.django_db
def test_administrator_cannot_grant_owner_role():
    organization = Organization.objects.create(name="Example", slug="example")
    admin_user = User.objects.create_user(email="admin@example.com", password="safe-test-password")
    member_user = User.objects.create_user(email="member@example.com", password="safe-test-password")
    admin = Membership.objects.create(
        organization=organization,
        user=admin_user,
        role=Role.ADMINISTRATOR,
        all_legal_entities=True,
    )
    member = Membership.objects.create(
        organization=organization,
        user=member_user,
        role=Role.MEMBER,
        all_legal_entities=True,
    )

    with pytest.raises(PermissionDenied):
        change_membership_role(
            actor_membership=admin,
            membership=member,
            role=Role.OWNER,
        )
