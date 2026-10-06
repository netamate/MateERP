from datetime import timedelta

import pytest
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.notifications.models import (
    DeliveryChannel,
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationKind,
)
from apps.operations.models import ServiceType, Subscription


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_refresh_notifications_uses_custom_offsets_and_deduplicates_delivery():
    owner = User.objects.create_user(email="notify-owner@example.com", password="test-pass-123")
    _, entity, _ = create_organization_with_owner(
        owner=owner,
        name="Notification Test",
        base_currency="USD",
    )
    today = timezone.localdate()
    subscription = Subscription.objects.create(
        legal_entity=entity,
        name="Example Service",
        service_type=ServiceType.SAAS,
        next_renewal_date=today + timedelta(days=5),
        amount="20.00",
        currency="USD",
        reminder_days=[5, 1, 0],
        reminder_in_app=True,
        reminder_email=True,
        reminder_email_recipients=["billing@example.com"],
    )

    call_command("refresh_notifications", horizon_days=30)
    call_command("refresh_notifications", horizon_days=30)

    notifications = Notification.objects.filter(
        recipient=owner,
        kind=NotificationKind.RENEWAL_DUE,
    )
    assert notifications.count() == 1
    assert notifications.get().resolved_at is None

    deliveries = NotificationDelivery.objects.filter(subscription=subscription)
    assert deliveries.filter(
        channel=DeliveryChannel.IN_APP,
        status=DeliveryStatus.SENT,
    ).count() == 1
    assert deliveries.filter(
        channel=DeliveryChannel.EMAIL,
        status=DeliveryStatus.SENT,
    ).count() == 1
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["billing@example.com"]
    assert "Cronjob" not in mail.outbox[0].body


@pytest.mark.django_db
def test_refresh_notifications_skips_days_not_in_custom_offsets():
    owner = User.objects.create_user(email="notify-skip@example.com", password="test-pass-123")
    _, entity, _ = create_organization_with_owner(
        owner=owner,
        name="Notification Skip Test",
        base_currency="USD",
    )
    today = timezone.localdate()
    Subscription.objects.create(
        legal_entity=entity,
        name="Later Service",
        next_renewal_date=today + timedelta(days=4),
        amount="12.00",
        currency="USD",
        reminder_days=[5, 1, 0],
    )

    call_command("refresh_notifications", horizon_days=30)

    assert Notification.objects.filter(recipient=owner).count() == 0
    assert NotificationDelivery.objects.count() == 0


@pytest.mark.django_db
@override_settings(MATEERP_HERMES_WEBHOOK_URL="", MATEERP_HERMES_WEBHOOK_TOKEN="")
def test_hermes_configuration_failure_is_recorded():
    User.objects.create_user(email="notify-hermes@example.com", password="test-pass-123")
    _, entity, _ = create_organization_with_owner(
        owner=User.objects.get(email="notify-hermes@example.com"),
        name="Hermes Test",
        base_currency="USD",
    )
    today = timezone.localdate()
    subscription = Subscription.objects.create(
        legal_entity=entity,
        name="Contabo VPS",
        service_type=ServiceType.VPS,
        next_renewal_date=today,
        amount="7.50",
        currency="EUR",
        reminder_days=[0],
        reminder_in_app=False,
        reminder_hermes=True,
        hermes_target="netamate-alerts",
    )

    call_command("refresh_notifications", horizon_days=30)

    delivery = NotificationDelivery.objects.get(
        subscription=subscription,
        channel=DeliveryChannel.HERMES,
    )
    assert delivery.status == DeliveryStatus.FAILED
    assert "MATEERP_HERMES_WEBHOOK_URL" in delivery.last_error
