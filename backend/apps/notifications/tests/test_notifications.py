from datetime import timedelta

import pytest
from apps.audit.models import AuditEvent
from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.notifications.crypto import decrypt_secret
from apps.notifications.models import (
    DeliveryChannel,
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationIntegrationSettings,
    NotificationKind,
)
from apps.operations.models import ServiceType, Subscription
from django.core import mail
from django.core.management import call_command
from django.test import Client, override_settings
from django.utils import timezone


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
    assert (
        deliveries.filter(
            channel=DeliveryChannel.IN_APP,
            status=DeliveryStatus.SENT,
        ).count()
        == 1
    )
    assert (
        deliveries.filter(
            channel=DeliveryChannel.EMAIL,
            status=DeliveryStatus.SENT,
        ).count()
        == 1
    )
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


@pytest.mark.django_db
def test_integration_settings_encrypt_secrets_and_never_return_them():
    owner = User.objects.create_user(
        email="integration-owner@example.com",
        password="test-pass-123",
    )
    organization, _, _ = create_organization_with_owner(
        owner=owner,
        name="Integration Settings Test",
        base_currency="USD",
    )
    client = Client()
    client.force_login(owner)
    session = client.session
    session["active_organization_id"] = str(organization.id)
    session.save()

    response = client.patch(
        "/api/v1/notifications/integrations/",
        data={
            "smtp_enabled": True,
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "alerts@example.com",
            "smtp_password": "smtp-secret-value",
            "smtp_use_tls": True,
            "smtp_use_ssl": False,
            "smtp_from_name": "MateERP",
            "smtp_from_email": "alerts@example.com",
            "hermes_enabled": True,
            "hermes_webhook_url": "https://hermes.example.com/hooks/mateerp",
            "hermes_token": "hermes-secret-value",
            "hermes_default_target": "netamate-alerts",
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["smtp_password_configured"] is True
    assert payload["hermes_token_configured"] is True
    assert "smtp_password" not in payload
    assert "hermes_token" not in payload
    assert "smtp_password_encrypted" not in payload
    assert "hermes_token_encrypted" not in payload

    integration = NotificationIntegrationSettings.objects.get(organization=organization)
    assert integration.smtp_password_encrypted != "smtp-secret-value"
    assert integration.hermes_token_encrypted != "hermes-secret-value"
    assert decrypt_secret(integration.smtp_password_encrypted) == "smtp-secret-value"
    assert decrypt_secret(integration.hermes_token_encrypted) == "hermes-secret-value"

    audit = AuditEvent.objects.filter(action="settings.notification_integrations_updated").latest(
        "created_at"
    )
    audit_text = str(audit.previous_state) + str(audit.new_state)
    assert "smtp-secret-value" not in audit_text
    assert "hermes-secret-value" not in audit_text


@pytest.mark.django_db
def test_integration_settings_blank_secret_fields_preserve_existing_secrets():
    owner = User.objects.create_user(
        email="integration-preserve@example.com",
        password="test-pass-123",
    )
    organization, _, _ = create_organization_with_owner(
        owner=owner,
        name="Integration Preserve Test",
        base_currency="USD",
    )
    client = Client()
    client.force_login(owner)
    session = client.session
    session["active_organization_id"] = str(organization.id)
    session.save()

    first = client.patch(
        "/api/v1/notifications/integrations/",
        data={
            "smtp_enabled": True,
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "alerts@example.com",
            "smtp_password": "first-secret",
            "smtp_use_tls": True,
            "smtp_from_email": "alerts@example.com",
        },
        content_type="application/json",
    )
    assert first.status_code == 200

    integration = NotificationIntegrationSettings.objects.get(organization=organization)
    encrypted_before = integration.smtp_password_encrypted

    second = client.patch(
        "/api/v1/notifications/integrations/",
        data={
            "smtp_from_name": "NetaMate ERP",
        },
        content_type="application/json",
    )
    assert second.status_code == 200

    integration.refresh_from_db()
    assert integration.smtp_password_encrypted == encrypted_before
    assert decrypt_secret(integration.smtp_password_encrypted) == "first-secret"
