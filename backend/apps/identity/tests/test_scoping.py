import pytest
from django.core.exceptions import PermissionDenied

from apps.identity.models import LegalEntity, Membership, Organization, User
from apps.identity.services import set_active_context


@pytest.mark.django_db
def test_user_cannot_select_unscoped_legal_entity():
    organization = Organization.objects.create(name="Example", slug="example")
    allowed = LegalEntity.objects.create(
        organization=organization,
        name="Allowed",
        slug="allowed",
    )
    denied = LegalEntity.objects.create(
        organization=organization,
        name="Denied",
        slug="denied",
    )
    user = User.objects.create_user(email="member@example.com", password="safe-test-password")
    membership = Membership.objects.create(organization=organization, user=user)
    membership.legal_entities.add(allowed)

    context = set_active_context(
        user=user,
        organization_id=organization.id,
        legal_entity_id=allowed.id,
    )
    assert context.legal_entity == allowed

    with pytest.raises(PermissionDenied):
        set_active_context(
            user=user,
            organization_id=organization.id,
            legal_entity_id=denied.id,
        )
