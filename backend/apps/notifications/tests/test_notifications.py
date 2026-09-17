from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.notifications.models import Notification, NotificationKind
from apps.operations.models import Domain


@pytest.mark.django_db
def test_refresh_notifications_deduplicates_and_resolves_renewal_alerts():
    owner = User.objects.create_user(email="notify-owner@example.com", password="test-pass-123")
    _, entity, _ = create_organization_with_owner(
        owner=owner,
        name="Notification Test",
        base_currency="USD",
    )
    today = timezone.localdate()
    domain = Domain.objects.create(
        legal_entity=entity,
        domain_name="example.test",
        registrar="Registrar",
        expiry_date=today + timedelta(days=5),
        renewal_amount="20.00",
        currency="USD",
    )

    call_command("refresh_notifications", horizon_days=30)
    call_command("refresh_notifications", horizon_days=30)

    notifications = Notification.objects.filter(
        recipient=owner,
        kind=NotificationKind.RENEWAL_DUE,
    )
    assert notifications.count() == 1
    assert notifications.get().resolved_at is None

    domain.expiry_date = today + timedelta(days=90)
    domain.save(update_fields=["expiry_date", "updated_at"])
    call_command("refresh_notifications", horizon_days=30)
    notifications.get().refresh_from_db()
    assert notifications.get().resolved_at is not None
