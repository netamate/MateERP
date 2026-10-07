from datetime import timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.utils import timezone

from apps.automation.models import AutomationKind, AutomationPolicy, RunStatus
from apps.automation.services import run_automation_policy
from apps.finance.models import Vendor
from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.notifications.models import (
    CentralEmailEvent,
    CentralEmailRecipient,
    DeliveryChannel,
    DeliveryStatus,
    NotificationDelivery,
    NotificationKind,
)
from apps.notifications.services import dispatch_document_uploaded_event
from apps.operations.models import Subscription, SubscriptionBillingPeriod
from apps.operations.services import (
    create_billing_payment,
    create_subscription_invoice,
)


def signed_in_owner(email="central-delivery-owner@example.com"):
    owner = User.objects.create_user(email=email, password="test-pass-123")
    organization, entity, membership = create_organization_with_owner(
        owner=owner,
        name=f"Central Delivery {email}",
        base_currency="USD",
    )
    client = Client()
    client.force_login(owner)
    session = client.session
    session["active_organization_id"] = str(organization.id)
    session["active_legal_entity_id"] = str(entity.id)
    session.save()
    return client, owner, organization, entity, membership


def pdf(name="invoice.pdf", marker=b"central-delivery"):
    return SimpleUploadedFile(
        name,
        b"%PDF-1.4\n" + marker + b"\n%%EOF",
        content_type="application/pdf",
    )


@pytest.mark.django_db(transaction=True)
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="MateERP <erp@example.com>",
)
def test_document_upload_sends_central_email_with_attachment_and_dedupes(tmp_path):
    client, _, organization, entity, _ = signed_in_owner()
    vendor = Vendor.objects.create(legal_entity=entity, code="OPENAI", name="OpenAI")
    subscription = Subscription.objects.create(
        legal_entity=entity,
        vendor=vendor,
        name="ChatGPT Plus",
        amount=Decimal("20.00"),
        currency="USD",
        email_notifications_enabled=True,
    )
    CentralEmailRecipient.objects.create(
        organization=organization,
        name="Finance",
        email="finance@example.com",
        event_types=[CentralEmailEvent.DOCUMENT_UPLOADED],
        attach_documents=True,
    )

    with override_settings(MEDIA_ROOT=tmp_path):
        response = client.post(
            "/api/v1/finance/documents/",
            data={
                "document_type": "INVOICE",
                "document_date": "2026-10-07",
                "reference": "INV-CENTRAL-1",
                "subscription": str(subscription.id),
                "file": pdf(),
            },
        )

        assert response.status_code == 201, response.content
        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.to == ["finance@example.com"]
        assert len(email.attachments) == 1
        assert email.attachments[0][0] == response.json()["standardized_name"]

        delivery = NotificationDelivery.objects.get(
            signal=NotificationKind.DOCUMENT_UPLOADED,
            source_id=response.json()["id"],
            channel=DeliveryChannel.EMAIL,
        )
        assert delivery.status == DeliveryStatus.SENT
        assert delivery.context["attach_document"] is True

        dispatch_document_uploaded_event(response.json()["id"])
        assert len(mail.outbox) == 1


@pytest.mark.django_db(transaction=True)
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="MateERP <erp@example.com>",
)
def test_subscription_toggle_suppresses_document_email(tmp_path):
    client, _, organization, entity, _ = signed_in_owner("central-delivery-disabled@example.com")
    subscription = Subscription.objects.create(
        legal_entity=entity,
        name="Disabled Email Subscription",
        amount=Decimal("10.00"),
        currency="USD",
        email_notifications_enabled=False,
    )
    CentralEmailRecipient.objects.create(
        organization=organization,
        email="finance@example.com",
        event_types=[CentralEmailEvent.DOCUMENT_UPLOADED],
    )

    with override_settings(MEDIA_ROOT=tmp_path):
        response = client.post(
            "/api/v1/finance/documents/",
            data={
                "document_type": "INVOICE",
                "document_date": "2026-10-07",
                "subscription": str(subscription.id),
                "file": pdf(marker=b"disabled"),
            },
        )

    assert response.status_code == 201, response.content
    assert len(mail.outbox) == 0
    assert not NotificationDelivery.objects.filter(
        signal=NotificationKind.DOCUMENT_UPLOADED,
        source_id=response.json()["id"],
    ).exists()


@pytest.mark.django_db(transaction=True)
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="MateERP <erp@example.com>",
)
def test_recipient_can_receive_document_notification_without_attachment(tmp_path):
    client, _, organization, entity, _ = signed_in_owner("central-delivery-link-only@example.com")
    subscription = Subscription.objects.create(
        legal_entity=entity,
        name="Link Only Subscription",
        amount=Decimal("10.00"),
        currency="USD",
        email_notifications_enabled=True,
    )
    CentralEmailRecipient.objects.create(
        organization=organization,
        email="audit@example.com",
        event_types=[CentralEmailEvent.DOCUMENT_UPLOADED],
        attach_documents=False,
    )

    with override_settings(MEDIA_ROOT=tmp_path):
        response = client.post(
            "/api/v1/finance/documents/",
            data={
                "document_type": "RECEIPT",
                "document_date": "2026-10-07",
                "subscription": str(subscription.id),
                "file": pdf(marker=b"link-only"),
            },
        )

    assert response.status_code == 201, response.content
    assert len(mail.outbox) == 1
    assert mail.outbox[0].attachments == []
    delivery = NotificationDelivery.objects.get(source_id=response.json()["id"])
    assert delivery.context["attachment_requested"] is False
    assert delivery.context["attach_document"] is False


@pytest.mark.django_db(transaction=True)
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="MateERP <erp@example.com>",
)
def test_invoice_and_payment_events_use_central_routing():
    _, owner, organization, entity, membership = signed_in_owner(
        "central-finance-events@example.com"
    )
    vendor = Vendor.objects.create(legal_entity=entity, code="VENDOR", name="Vendor")
    subscription = Subscription.objects.create(
        legal_entity=entity,
        vendor=vendor,
        name="Managed Service",
        amount=Decimal("25.00"),
        currency="USD",
        email_notifications_enabled=True,
    )
    CentralEmailRecipient.objects.create(
        organization=organization,
        email="finance@example.com",
        event_types=[
            CentralEmailEvent.INVOICE_RECORDED,
            CentralEmailEvent.PAYMENT_RECORDED,
        ],
    )
    today = timezone.localdate()
    period = SubscriptionBillingPeriod.objects.create(
        legal_entity=entity,
        subscription=subscription,
        period_start=today - timedelta(days=30),
        period_end=today,
        estimated_cost=Decimal("25.00"),
        created_by=owner,
    )

    invoice = create_subscription_invoice(
        membership=membership,
        billing_period=period,
        invoice_number="INV-EVENT-1",
        invoice_date=today,
        currency="USD",
        subtotal=Decimal("25.00"),
        tax_amount=Decimal("0"),
        total_amount=Decimal("25.00"),
    )
    assert invoice.invoice_number == "INV-EVENT-1"

    payment = create_billing_payment(
        membership=membership,
        subscription=subscription,
        paid_on=today,
        amount=Decimal("25.00"),
        currency="USD",
        reference="PAY-EVENT-1",
    )
    assert payment.reference == "PAY-EVENT-1"

    assert len(mail.outbox) == 2
    assert (
        NotificationDelivery.objects.filter(
            signal=NotificationKind.INVOICE_RECORDED,
            status=DeliveryStatus.SENT,
        ).count()
        == 1
    )
    assert (
        NotificationDelivery.objects.filter(
            signal=NotificationKind.PAYMENT_RECORDED,
            status=DeliveryStatus.SENT,
        ).count()
        == 1
    )


@pytest.mark.django_db(transaction=True)
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="MateERP <erp@example.com>",
)
def test_organization_level_automation_failure_can_be_delivered(monkeypatch):
    _, owner, organization, _, _ = signed_in_owner("central-automation@example.com")
    CentralEmailRecipient.objects.create(
        organization=organization,
        email="ops@example.com",
        event_types=[CentralEmailEvent.AUTOMATION_FAILURE],
    )
    policy = AutomationPolicy.objects.create(
        organization=organization,
        name="Failing PAYG automation",
        kind=AutomationKind.ENSURE_PAYG_PERIODS,
        created_by=owner,
        updated_by=owner,
    )

    def fail_policy(*args, **kwargs):
        raise RuntimeError("forced automation failure")

    monkeypatch.setattr("apps.automation.services._ensure_periods", fail_policy)
    run = run_automation_policy(policy, actor=owner)

    assert run.status == RunStatus.FAILED
    assert len(mail.outbox) == 1
    delivery = NotificationDelivery.objects.get(signal=NotificationKind.AUTOMATION_FAILURE)
    assert delivery.legal_entity is None
    assert delivery.status == DeliveryStatus.SENT
    assert "forced automation failure" in delivery.message


@pytest.mark.django_db
def test_central_delivery_history_filter_exposes_context_and_scope():
    client, _, organization, entity, _ = signed_in_owner("central-history@example.com")
    central = NotificationDelivery.objects.create(
        organization=organization,
        legal_entity=entity,
        delivery_key="central:history-one",
        signal=NotificationKind.DOCUMENT_UPLOADED,
        source_type="FinanceDocument",
        source_id="doc-1",
        channel=DeliveryChannel.EMAIL,
        destination="finance@example.com",
        title="Document uploaded",
        message="A document was uploaded.",
        context={
            "central_email_event": CentralEmailEvent.DOCUMENT_UPLOADED,
            "recipient_type": "TO",
            "attachment_requested": True,
            "attach_document": True,
        },
    )
    NotificationDelivery.objects.create(
        organization=organization,
        legal_entity=entity,
        delivery_key="legacy:history-two",
        signal=NotificationKind.RENEWAL_DUE,
        source_type="Subscription",
        source_id="sub-1",
        channel=DeliveryChannel.EMAIL,
        destination="legacy@example.com",
        title="Legacy delivery",
        message="Legacy delivery",
    )

    response = client.get("/api/v1/notifications/deliveries/?central_only=true&channel=EMAIL")

    assert response.status_code == 200, response.content
    rows = response.json()["results"]
    assert [row["id"] for row in rows] == [str(central.id)]
    assert rows[0]["central_delivery"] is True
    assert rows[0]["legal_entity"] == str(entity.id)
    assert rows[0]["legal_entity_name"] == entity.name
    assert rows[0]["context"]["attach_document"] is True
    assert rows[0]["context"]["recipient_type"] == "TO"


@pytest.mark.django_db
def test_organization_level_central_delivery_can_retry_with_active_entity(monkeypatch):
    client, _, organization, _, _ = signed_in_owner("central-org-retry@example.com")
    delivery = NotificationDelivery.objects.create(
        organization=organization,
        legal_entity=None,
        delivery_key="central:org-retry",
        signal=NotificationKind.AUTOMATION_FAILURE,
        source_type="AutomationRun",
        source_id="run-1",
        channel=DeliveryChannel.EMAIL,
        destination="ops@example.com",
        title="Automation failed",
        message="Retry me",
        email_subject="Automation failed",
        email_text_body="Retry me",
        status=DeliveryStatus.FAILED,
        last_error="Temporary SMTP failure",
        context={
            "central_email_event": CentralEmailEvent.AUTOMATION_FAILURE,
            "recipient_type": "TO",
        },
    )

    monkeypatch.setattr(
        "apps.notifications.services._send_email",
        lambda **kwargs: None,
    )
    response = client.post(f"/api/v1/notifications/deliveries/{delivery.id}/retry/")

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["status"] == DeliveryStatus.SENT
    assert payload["central_delivery"] is True
    assert payload["attempt_count"] == 1
