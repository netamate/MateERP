import pytest
from django.core.management import call_command

from apps.identity.models import Membership, Role, User


@pytest.mark.django_db
def test_bootstrap_can_create_owner_and_django_superuser(monkeypatch):
    monkeypatch.setenv("MATEERP_BOOTSTRAP_PASSWORD", "Bootstrap-Test-Password-4831!")

    call_command(
        "bootstrap_instance",
        email="owner@example.com",
        organization="Example Organization",
        legal_entity="Example Legal Entity",
        display_name="Example Owner",
        timezone="UTC",
        base_currency="USD",
        django_superuser=True,
    )

    user = User.objects.get(email="owner@example.com")
    membership = Membership.objects.get(user=user)

    assert user.display_name == "Example Owner"
    assert user.is_staff is True
    assert user.is_superuser is True
    assert membership.role == Role.OWNER
    assert user.check_password("Bootstrap-Test-Password-4831!")
