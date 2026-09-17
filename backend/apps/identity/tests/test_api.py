import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.identity.models import LegalEntity, Membership, Organization, Role, User


@pytest.mark.django_db
def test_session_requires_authentication():
    client = APIClient()
    response = client.get(reverse("session"))
    assert response.status_code in {401, 403}


@pytest.mark.django_db
def test_authenticated_session_is_scoped_to_memberships():
    user = User.objects.create_user(email="owner@example.com", password="safe-test-password")
    organization = Organization.objects.create(name="Example", slug="example")
    entity = LegalEntity.objects.create(
        organization=organization,
        name="Example",
        slug="example",
    )
    Membership.objects.create(
        organization=organization,
        user=user,
        role=Role.OWNER,
        all_legal_entities=True,
    )
    client = APIClient()
    client.force_login(user)

    session = client.session
    session["active_organization_id"] = str(organization.id)
    session["active_legal_entity_id"] = str(entity.id)
    session.save()

    response = client.get(reverse("session"))
    assert response.status_code == 200
    assert response.data["active_organization_id"] == str(organization.id)
    assert response.data["active_legal_entity_id"] == str(entity.id)
    assert response.data["memberships"][0]["role"] == Role.OWNER
