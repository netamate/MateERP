from decimal import Decimal

import pytest
from django.core import mail
from django.test import Client, override_settings
from django.utils import timezone

from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.notifications.models import (
    AlertRule,
    DeliveryChannel,
    EmailTemplate,
    NotificationDelivery,
    NotificationKind,
)
from apps.operations.models import Subscription


def signed_in_owner(email="template-owner@example.com"):
    owner = User.objects.create_user(email=email, password="test-pass-123")
    organization, entity, _ = create_organization_with_owner(
        owner=owner,
        name="Template Test Org",
        base_currency="USD",
    )
    client = Client()
    client.force_login(owner)
    session = client.session
    session["active_organization_id"] = str(organization.id)
    session["active_legal_entity_id"] = str(entity.id)
    session.save()
    return client, owner, organization, entity


def post_json(client, path, payload):
    return client.post(path, data=payload, content_type="application/json")


def patch_json(client, path, payload):
    return client.patch(path, data=payload, content_type="application/json")


@pytest.mark.django_db
def test_default_templates_are_seeded_and_preview_is_sanitized():
    client, _, organization, _ = signed_in_owner()

    listed = client.get("/api/v1/notifications/email-templates/")
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 6
    assert EmailTemplate.objects.filter(organization=organization).count() == 6
    assert all(row["current_version"] == 1 for row in rows)

    preview = post_json(
        client,
        "/api/v1/notifications/email-templates/preview/",
        {
            "signal": "BUDGET_THRESHOLD",
            "subject_template": "{{alert_title}}",
            "text_body_template": "{{alert_message}}",
            "html_body_template": (
                '<div><script>alert(1)</script>'
                '<a href="javascript:alert(1)">{{alert_message}}</a>'
                '<strong>{{subscription_name}}</strong></div>'
            ),
            "context": {
                "alert_title": "Budget warning",
                "alert_message": "<unsafe>",
                "subscription_name": "Azure PAYG",
            },
        },
    )
    assert preview.status_code == 200, preview.content
    body = preview.json()
    assert body["subject"] == "Budget warning"
    assert "<script" not in body["html_body"].lower()
    assert "javascript:" not in body["html_body"].lower()
    assert "&lt;unsafe&gt;" in body["html_body"]
    assert "Azure PAYG" in body["html_body"]


@pytest.mark.django_db
def test_template_content_update_creates_immutable_version_but_status_change_does_not():
    client, _, organization, _ = signed_in_owner("version-owner@example.com")
    created = post_json(
        client,
        "/api/v1/notifications/email-templates/",
        {
            "template_key": "finance-custom",
            "name": "Finance Custom",
            "description": "Custom finance alert",
            "signal": "INVOICE_OVERDUE",
            "subject_template": "Invoice {{invoice_number}} overdue",
            "text_body_template": "{{alert_message}}",
            "html_body_template": "<p>{{alert_message}}</p>",
            "status": "ACTIVE",
        },
    )
    assert created.status_code == 201, created.content
    template = created.json()
    assert template["current_version"] == 1

    updated = patch_json(
        client,
        f"/api/v1/notifications/email-templates/{template['id']}/",
        {"subject_template": "Overdue: {{invoice_number}}"},
    )
    assert updated.status_code == 200, updated.content
    assert updated.json()["current_version"] == 2

    versions = client.get(
        f"/api/v1/notifications/email-templates/{template['id']}/versions/"
    )
    assert versions.status_code == 200
    assert [row["version_number"] for row in versions.json()] == [2, 1]

    status_only = patch_json(
        client,
        f"/api/v1/notifications/email-templates/{template['id']}/",
        {"status": "ARCHIVED"},
    )
    assert status_only.status_code == 200
    assert status_only.json()["current_version"] == 2
    assert EmailTemplate.objects.get(
        organization=organization,
        id=template["id"],
    ).versions.count() == 2


@pytest.mark.django_db
def test_unknown_template_variable_is_rejected():
    client, _, _, _ = signed_in_owner("invalid-variable@example.com")
    response = post_json(
        client,
        "/api/v1/notifications/email-templates/",
        {
            "template_key": "invalid-token",
            "name": "Invalid Token",
            "signal": "MISSING_INVOICE",
            "subject_template": "{{made_up_variable}}",
            "text_body_template": "{{alert_message}}",
            "html_body_template": "<p>{{alert_message}}</p>",
        },
    )
    assert response.status_code == 400
    assert "made_up_variable" in str(response.json())


@pytest.mark.django_db
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="NetaMate ERP <erp@netamate.com>",
)
def test_direct_email_preserves_template_version_and_sends_html_alternative():
    client, _, _, _ = signed_in_owner("direct-template@example.com")
    templates = client.get("/api/v1/notifications/email-templates/").json()
    general = next(row for row in templates if row["signal"] is None)

    preview = post_json(
        client,
        "/api/v1/notifications/email-templates/preview/",
        {
            "signal": None,
            "subject_template": general["subject_template"],
            "text_body_template": general["text_body_template"],
            "html_body_template": general["html_body_template"],
            "context": {"alert_message": "Quarterly finance update"},
        },
    )
    assert preview.status_code == 200, preview.content
    rendered = preview.json()

    sent = post_json(
        client,
        "/api/v1/notifications/email/",
        {
            "action": "SEND_NOW",
            "template": general["id"],
            "to_recipients": ["finance@example.com"],
            "cc_recipients": [],
            "bcc_recipients": [],
            "subject": rendered["subject"],
            "body": rendered["text_body"],
            "html_body": rendered["html_body"],
            "schedule_timezone": "UTC",
        },
    )
    assert sent.status_code == 201, sent.content
    payload = sent.json()
    assert payload["status"] == "SENT"
    assert payload["template"] == general["id"]
    assert payload["template_version"] == 1
    assert payload["template_name"] == general["name"]
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["finance@example.com"]
    assert mail.outbox[0].alternatives
    assert mail.outbox[0].alternatives[0].mimetype == "text/html"


@pytest.mark.django_db
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="NetaMate ERP <erp@netamate.com>",
)
def test_alert_email_delivery_snapshots_template_content_and_version():
    client, owner, organization, entity = signed_in_owner("alert-template@example.com")
    client.get("/api/v1/notifications/rules/")
    custom = post_json(
        client,
        "/api/v1/notifications/email-templates/",
        {
            "template_key": "renewal-custom",
            "name": "Renewal Custom",
            "signal": "RENEWAL_DUE",
            "subject_template": "Renewal: {{subscription_name}}",
            "text_body_template": "{{alert_message}}",
            "html_body_template": "<h2>{{subscription_name}}</h2><p>{{alert_message}}</p>",
        },
    )
    assert custom.status_code == 201, custom.content
    template = custom.json()

    rule = AlertRule.objects.get(
        organization=organization,
        signal=NotificationKind.RENEWAL_DUE,
        legal_entity__isnull=True,
    )
    patched = patch_json(
        client,
        f"/api/v1/notifications/rules/{rule.id}/",
        {
            "email_template": template["id"],
            "in_app_enabled": False,
            "email_enabled": False,
            "respect_subscription_channels": True,
        },
    )
    assert patched.status_code == 200, patched.content

    subscription = Subscription.objects.create(
        legal_entity=entity,
        name="ChatGPT Plus",
        amount=Decimal("20.00"),
        currency="USD",
        next_renewal_date=timezone.localdate(),
        reminder_days=[0],
        reminder_in_app=False,
        reminder_email=True,
        reminder_email_recipients=[owner.email],
    )

    run = post_json(
        client,
        "/api/v1/notifications/rules/run-now/",
        {},
    )
    assert run.status_code == 200, run.content
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "Renewal: ChatGPT Plus"
    assert mail.outbox[0].alternatives

    delivery = NotificationDelivery.objects.get(
        subscription=subscription,
        channel=DeliveryChannel.EMAIL,
    )
    assert delivery.email_template_id == template["id"]
    assert delivery.email_template_version == 1
    assert delivery.email_subject == "Renewal: ChatGPT Plus"
    first_html = delivery.email_html_body
    assert "ChatGPT Plus" in first_html

    updated = patch_json(
        client,
        f"/api/v1/notifications/email-templates/{template['id']}/",
        {"html_body_template": "<h1>NEW VERSION</h1><p>{{alert_message}}</p>"},
    )
    assert updated.status_code == 200
    assert updated.json()["current_version"] == 2

    second_run = post_json(
        client,
        "/api/v1/notifications/rules/run-now/",
        {},
    )
    assert second_run.status_code == 200
    assert len(mail.outbox) == 1
    delivery.refresh_from_db()
    assert delivery.email_template_version == 1
    assert delivery.email_html_body == first_html
