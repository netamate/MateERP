from unittest.mock import patch

import pytest
from django.test import Client

from apps.audit.models import AuditEvent
from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.notifications.crypto import encrypt_secret
from apps.notifications.models import NotificationIntegrationSettings


def owner_client():
    owner = User.objects.create_user(
        email="smtp-preview-owner@example.com", password="test-pass-123"
    )
    organization, _, _ = create_organization_with_owner(
        owner=owner, name="SMTP Preview Test", base_currency="USD"
    )
    client = Client()
    client.force_login(owner)
    session = client.session
    session["active_organization_id"] = str(organization.id)
    session.save()
    return client, organization


def smtp_draft(**updates):
    body = {
        "recipient": "receive@example.com",
        "smtp_enabled": True,
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_username": "sender@example.com",
        "smtp_password": "unsaved-secret",
        "smtp_use_tls": True,
        "smtp_use_ssl": False,
        "smtp_from_name": "Preview Sender",
        "smtp_from_email": "sender@example.com",
    }
    body.update(updates)
    return body


@pytest.mark.django_db
def test_smtp_preview_uses_unsaved_fields_and_does_not_persist():
    client, organization = owner_client()
    with (
        patch("apps.notifications.services.get_connection") as get_connection,
        patch("apps.notifications.services.EmailMultiAlternatives") as email_class,
    ):
        response = client.post(
            "/api/v1/notifications/integrations/test-email/",
            data=smtp_draft(),
            content_type="application/json",
        )
    assert response.status_code == 200
    assert "have not been saved" in response.json()["detail"]
    assert get_connection.call_args.kwargs["host"] == "smtp.example.com"
    assert get_connection.call_args.kwargs["password"] == "unsaved-secret"
    assert get_connection.call_args.kwargs["use_tls"] is True
    email_class.return_value.send.assert_called_once_with(fail_silently=False)
    assert not NotificationIntegrationSettings.objects.filter(organization=organization).exists()
    log = AuditEvent.objects.get(action="settings.smtp_test_sent")
    assert "unsaved-secret" not in str(log.new_state)


@pytest.mark.django_db
def test_smtp_preview_requires_enabled_draft_with_clear_error():
    client, organization = owner_client()
    response = client.post(
        "/api/v1/notifications/integrations/test-email/",
        data=smtp_draft(smtp_enabled=False),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "Enable direct email" in str(response.json())
    assert not NotificationIntegrationSettings.objects.filter(organization=organization).exists()


@pytest.mark.django_db
def test_smtp_preview_reuses_stored_password_without_overwriting_settings():
    client, organization = owner_client()
    original = NotificationIntegrationSettings.objects.create(
        organization=organization,
        smtp_enabled=False,
        smtp_host="previous.example.com",
        smtp_port=465,
        smtp_username="previous@example.com",
        smtp_password_encrypted=encrypt_secret("saved-secret"),
        smtp_use_ssl=True,
    )
    body = smtp_draft()
    body.pop("smtp_password")
    with (
        patch("apps.notifications.services.get_connection") as get_connection,
        patch("apps.notifications.services.EmailMultiAlternatives"),
    ):
        response = client.post(
            "/api/v1/notifications/integrations/test-email/",
            data=body,
            content_type="application/json",
        )
    assert response.status_code == 200
    assert get_connection.call_args.kwargs["password"] == "saved-secret"
    original.refresh_from_db()
    assert original.smtp_enabled is False
    assert original.smtp_host == "previous.example.com"


@pytest.mark.django_db
def test_smtp_auth_rejection_is_400_not_500_and_does_not_echo_server_response():
    from smtplib import SMTPAuthenticationError

    client, organization = owner_client()
    with patch(
        "apps.notifications.services.get_connection",
        side_effect=SMTPAuthenticationError(535, b"private authentication details"),
    ):
        response = client.post(
            "/api/v1/notifications/integrations/test-email/",
            data=smtp_draft(),
            content_type="application/json",
        )
    assert response.status_code == 400
    assert "authentication was rejected" in str(response.json())
    assert "private authentication details" not in str(response.json())
    assert not NotificationIntegrationSettings.objects.filter(organization=organization).exists()
