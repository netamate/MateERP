import hashlib
import hmac
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.notifications.crypto import encrypt_secret
from apps.notifications.models import (
    DeliveryChannel,
    DeliveryStatus,
    DirectEmailNotification,
    DirectEmailStatus,
    NotificationIntegrationSettings,
)
from apps.notifications.services import deliver_hermes
from apps.operations.models import ServiceType, Subscription
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone


@pytest.mark.django_db
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="NetaMate ERP <erp@netamate.com>",
)
def test_due_direct_email_is_sent_by_scheduler():
    owner = User.objects.create_user(
        email="direct-email-owner@example.com",
        password="test-pass-123",
    )
    organization, entity, _ = create_organization_with_owner(
        owner=owner,
        name="Direct Email Test",
        base_currency="USD",
    )
    notification = DirectEmailNotification.objects.create(
        organization=organization,
        legal_entity=entity,
        created_by=owner,
        to_recipients=["rizwan@example.com", "finance@example.com"],
        cc_recipients=["ops@example.com"],
        subject="Renewal reminder",
        body="A scheduled reminder from MateERP.",
        scheduled_for=timezone.now() - timedelta(minutes=1),
        schedule_timezone="Asia/Dhaka",
        status=DirectEmailStatus.SCHEDULED,
    )

    call_command("process_scheduled_emails")

    notification.refresh_from_db()
    assert notification.status == DirectEmailStatus.SENT
    assert notification.attempt_count == 1
    assert notification.sent_at is not None
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["rizwan@example.com", "finance@example.com"]
    assert mail.outbox[0].cc == ["ops@example.com"]


@pytest.mark.django_db
def test_hermes_uses_native_hmac_v2_headers_instead_of_bearer_token():
    owner = User.objects.create_user(
        email="hmac-owner@example.com",
        password="test-pass-123",
    )
    organization, entity, _ = create_organization_with_owner(
        owner=owner,
        name="Hermes HMAC Test",
        base_currency="USD",
    )
    secret = "a-strong-shared-webhook-secret"
    NotificationIntegrationSettings.objects.create(
        organization=organization,
        hermes_enabled=True,
        hermes_webhook_url="https://hermes.example.com/webhooks/mateerp-alerts",
        hermes_token_encrypted=encrypt_secret(secret),
    )
    subscription = Subscription.objects.create(
        legal_entity=entity,
        name="Contabo VPS",
        service_type=ServiceType.VPS,
        next_renewal_date=timezone.localdate(),
        amount="7.50",
        currency="EUR",
        reminder_days=[0],
        reminder_in_app=False,
        reminder_hermes=True,
    )

    response = MagicMock()
    response.__enter__.return_value.status = 202
    with patch(
        "apps.notifications.services.request.urlopen",
        return_value=response,
    ) as mocked_open:
        delivery = deliver_hermes(
            subscription=subscription,
            destination="",
            days_before=0,
            due_date=subscription.next_renewal_date,
            title="Payment due today",
            message="Contabo VPS is due today.",
        )

    assert delivery.channel == DeliveryChannel.HERMES
    assert delivery.status == DeliveryStatus.SENT
    webhook_request = mocked_open.call_args.args[0]
    headers = {key.lower(): value for key, value in webhook_request.header_items()}
    assert "authorization" not in headers
    assert "x-webhook-timestamp" in headers
    assert "x-webhook-signature-v2" in headers
    expected = hmac.new(
        secret.encode(),
        headers["x-webhook-timestamp"].encode() + b"." + webhook_request.data,
        hashlib.sha256,
    ).hexdigest()
    assert hmac.compare_digest(headers["x-webhook-signature-v2"], expected)
