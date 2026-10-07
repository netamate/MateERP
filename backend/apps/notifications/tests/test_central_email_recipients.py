import pytest
from django.test import Client

from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.notifications.models import (
    CentralEmailEvent,
    CentralEmailRecipient,
    CentralEmailRecipientType,
)
from apps.notifications.services import resolve_central_email_recipients
from apps.operations.models import Subscription


def signed_in_owner(email="central-email-owner@example.com"):
    owner = User.objects.create_user(email=email, password="test-pass-123")
    organization, entity, _ = create_organization_with_owner(
        owner=owner,
        name=f"Central Email {email}",
        base_currency="USD",
    )
    client = Client()
    client.force_login(owner)
    session = client.session
    session["active_organization_id"] = str(organization.id)
    session["active_legal_entity_id"] = str(entity.id)
    session.save()
    return client, owner, organization, entity


@pytest.mark.django_db
def test_central_recipient_crud_normalizes_email_and_exposes_event_catalog():
    client, _, organization, _ = signed_in_owner()

    events = client.get("/api/v1/notifications/central-recipients/events/")
    assert events.status_code == 200
    assert {row["value"] for row in events.json()} >= {
        CentralEmailEvent.DOCUMENT_UPLOADED,
        CentralEmailEvent.RENEWAL_DUE,
        CentralEmailEvent.AUTOMATION_FAILURE,
    }

    created = client.post(
        "/api/v1/notifications/central-recipients/",
        data={
            "name": "Finance",
            "email": "Finance@Example.COM",
            "recipient_type": CentralEmailRecipientType.TO,
            "enabled": True,
            "event_types": [
                CentralEmailEvent.DOCUMENT_UPLOADED,
                CentralEmailEvent.INVOICE_RECORDED,
            ],
            "attach_documents": True,
        },
        content_type="application/json",
    )
    assert created.status_code == 201, created.content
    payload = created.json()
    assert payload["email"] == "finance@example.com"
    assert payload["event_types"] == [
        CentralEmailEvent.DOCUMENT_UPLOADED,
        CentralEmailEvent.INVOICE_RECORDED,
    ]
    assert CentralEmailRecipient.objects.filter(organization=organization).count() == 1

    updated = client.patch(
        f"/api/v1/notifications/central-recipients/{payload['id']}/",
        data={
            "recipient_type": CentralEmailRecipientType.CC,
            "enabled": False,
        },
        content_type="application/json",
    )
    assert updated.status_code == 200, updated.content
    assert updated.json()["recipient_type"] == CentralEmailRecipientType.CC
    assert updated.json()["enabled"] is False

    removed = client.delete(
        f"/api/v1/notifications/central-recipients/{payload['id']}/"
    )
    assert removed.status_code == 204
    assert CentralEmailRecipient.objects.filter(organization=organization).count() == 0


@pytest.mark.django_db
def test_central_recipient_rejects_duplicate_and_unknown_event():
    client, _, _, _ = signed_in_owner("central-email-validation@example.com")
    body = {
        "name": "Finance",
        "email": "finance@example.com",
        "recipient_type": CentralEmailRecipientType.TO,
        "enabled": True,
        "event_types": [CentralEmailEvent.DOCUMENT_UPLOADED],
        "attach_documents": True,
    }

    first = client.post(
        "/api/v1/notifications/central-recipients/",
        data=body,
        content_type="application/json",
    )
    assert first.status_code == 201, first.content

    duplicate = client.post(
        "/api/v1/notifications/central-recipients/",
        data={**body, "email": "FINANCE@example.com"},
        content_type="application/json",
    )
    assert duplicate.status_code == 400

    invalid = client.patch(
        f"/api/v1/notifications/central-recipients/{first.json()['id']}/",
        data={"event_types": ["NOT_A_REAL_EVENT"]},
        content_type="application/json",
    )
    assert invalid.status_code == 400


@pytest.mark.django_db
def test_event_recipient_resolver_groups_roles_and_ignores_disabled_rows():
    _, owner, organization, _ = signed_in_owner("central-email-resolver@example.com")
    CentralEmailRecipient.objects.create(
        organization=organization,
        name="Finance",
        email="finance@example.com",
        recipient_type=CentralEmailRecipientType.TO,
        event_types=[
            CentralEmailEvent.DOCUMENT_UPLOADED,
            CentralEmailEvent.INVOICE_RECORDED,
        ],
        created_by=owner,
        updated_by=owner,
    )
    CentralEmailRecipient.objects.create(
        organization=organization,
        name="Director",
        email="director@example.com",
        recipient_type=CentralEmailRecipientType.CC,
        event_types=[CentralEmailEvent.DOCUMENT_UPLOADED],
        created_by=owner,
        updated_by=owner,
    )
    CentralEmailRecipient.objects.create(
        organization=organization,
        name="Disabled",
        email="disabled@example.com",
        recipient_type=CentralEmailRecipientType.BCC,
        enabled=False,
        event_types=[CentralEmailEvent.DOCUMENT_UPLOADED],
        created_by=owner,
        updated_by=owner,
    )

    resolved = resolve_central_email_recipients(
        organization=organization,
        event_type=CentralEmailEvent.DOCUMENT_UPLOADED,
    )

    assert resolved == {
        "to": ["finance@example.com"],
        "cc": ["director@example.com"],
        "bcc": [],
    }


@pytest.mark.django_db
def test_subscription_exposes_only_central_email_opt_in_as_writable_email_setting():
    client, _, _, entity = signed_in_owner("central-email-subscription@example.com")

    created = client.post(
        "/api/v1/operations/subscriptions/",
        data={
            "name": "Contabo VPS",
            "amount": "10.00",
            "currency": "USD",
            "email_notifications_enabled": True,
            "reminder_email": True,
            "reminder_email_recipients": ["legacy@example.com"],
        },
        content_type="application/json",
    )
    assert created.status_code == 201, created.content
    payload = created.json()
    assert payload["email_notifications_enabled"] is True
    assert payload["reminder_email"] is False
    assert payload["reminder_email_recipients"] == []

    subscription = Subscription.objects.get(id=payload["id"], legal_entity=entity)
    assert subscription.email_notifications_enabled is True
    assert subscription.reminder_email is False
    assert subscription.reminder_email_recipients == []
