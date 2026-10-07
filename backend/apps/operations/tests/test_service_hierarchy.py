"""Phase 1: multiple billing identities under one vendor service, safely scoped."""

import pytest
from django.test import Client

from apps.audit.models import AuditEvent
from apps.finance.models import Vendor
from apps.identity.models import User
from apps.identity.services import create_organization_with_owner
from apps.operations.models import ServiceAccount, Subscription, VendorService


def logged_in_context(email, name):
    owner = User.objects.create_user(email=email, password="test-password-123")
    organization, entity, _ = create_organization_with_owner(
        owner=owner, name=name, base_currency="USD"
    )
    client = Client()
    client.force_login(owner)
    session = client.session
    session["active_organization_id"] = str(organization.id)
    session["active_legal_entity_id"] = str(entity.id)
    session.save()
    return client, entity


def json_post(client, path, body):
    return client.post(path, data=body, content_type="application/json")


def json_patch(client, path, body):
    return client.patch(path, data=body, content_type="application/json")


@pytest.mark.django_db
def test_vendor_service_account_crud_and_subscription_aliases():
    client, entity = logged_in_context("owner-hierarchy@example.com", "Hierarchy Org")
    vendor = Vendor.objects.create(legal_entity=entity, name="OpenAI", code="OPENAI")

    service_response = json_post(
        client,
        "/api/v1/operations/vendor-services/",
        {
            "vendor": str(vendor.id),
            "name": "ChatGPT",
            "code": "chatgpt",
            "service_type": "AI",
        },
    )
    assert service_response.status_code == 201, service_response.content
    service = service_response.json()
    assert service["code"] == "CHATGPT"
    assert service["vendor_name"] == "OpenAI"

    for alias in ("Rizwan-01", "Shahbaj-01"):
        response = json_post(
            client,
            "/api/v1/operations/service-accounts/",
            {"service": service["id"], "alias": alias},
        )
        assert response.status_code == 201, response.content
        assert response.json()["code"].startswith("ACC-")

    accounts = client.get("/api/v1/operations/service-accounts/").json()
    assert len(accounts) == 2
    assert accounts[0]["code"] != accounts[1]["code"]

    created_ids = []
    for account in accounts:
        response = json_post(
            client,
            "/api/v1/operations/subscriptions/",
            {
                "vendor": str(vendor.id),
                "service": service["id"],
                "service_account": account["id"],
                "name": "ChatGPT Plus",
                "service_type": "AI",
                "amount": "20.00",
                "currency": "USD",
                "billing_cycle": "MONTHLY",
            },
        )
        assert response.status_code == 201, response.content
        body = response.json()
        assert body["account_alias"] == account["alias"]
        assert body["vendor_service_name"] == "ChatGPT"
        assert body["subscription_code"].startswith("SUB-")
        created_ids.append(body["subscription_code"])
    assert len(set(created_ids)) == 2
    assert Subscription.objects.filter(legal_entity=entity).count() == 2
    assert AuditEvent.objects.filter(
        action="operations.service_account_created"
    ).count() == 2

    renamed = json_patch(
        client,
        f"/api/v1/operations/service-accounts/{accounts[0]['id']}/",
        {"alias": "Rizwan-Main"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["code"] == accounts[0]["code"]
    assert sorted(
        Subscription.objects.filter(legal_entity=entity).values_list(
            "subscription_code", flat=True
        )
    ) == sorted(created_ids)


@pytest.mark.django_db
def test_scope_checks_and_case_insensitive_account_alias():
    first, entity1 = logged_in_context("hierarchy-first@example.com", "First Organization")
    second, entity2 = logged_in_context("hierarchy-second@example.com", "Second Organization")
    vendor1 = Vendor.objects.create(legal_entity=entity1, name="OpenAI", code="OAI")
    vendor2 = Vendor.objects.create(legal_entity=entity2, name="Cloud", code="CLOUD")
    service1 = VendorService.objects.create(
        legal_entity=entity1, vendor=vendor1, code="CHATGPT", name="ChatGPT"
    )
    service2 = VendorService.objects.create(
        legal_entity=entity2, vendor=vendor2, code="CLOUD", name="Cloud"
    )
    account1 = ServiceAccount.objects.create(
        legal_entity=entity1, service=service1, alias="Rizwan-01"
    )

    result = json_post(
        second,
        "/api/v1/operations/service-accounts/",
        {"service": str(service1.id), "alias": "Other"},
    )
    assert result.status_code == 400

    duplicated = json_post(
        first,
        "/api/v1/operations/service-accounts/",
        {"service": str(service1.id), "alias": "rizwan-01"},
    )
    assert duplicated.status_code == 400

    cross_vendor = json_post(
        first,
        "/api/v1/operations/vendor-services/",
        {"vendor": str(vendor2.id), "name": "Wrong", "code": "WRONG"},
    )
    assert cross_vendor.status_code == 400

    cross_account = json_post(
        second,
        "/api/v1/operations/subscriptions/",
        {
            "vendor": str(vendor2.id),
            "service": str(service2.id),
            "service_account": str(account1.id),
            "name": "Cloud Tier",
            "amount": "10.00",
        },
    )
    assert cross_account.status_code == 400

    moved = json_patch(
        first,
        f"/api/v1/operations/service-accounts/{account1.id}/",
        {"service": str(service2.id)},
    )
    assert moved.status_code == 400

    invisible = second.get(f"/api/v1/operations/service-accounts/{account1.id}/")
    assert invisible.status_code == 405  # detail only supports PATCH; no cross-tenant data


@pytest.mark.django_db
def test_existing_subscription_preserved_and_can_be_assigned_later():
    client, entity = logged_in_context("legacy-owner@example.com", "Legacy Org")
    vendor = Vendor.objects.create(legal_entity=entity, name="Namecheap", code="NAMECHEAP")
    legacy = Subscription.objects.create(
        legal_entity=entity, vendor=vendor, name="netamate.com", amount="18"
    )
    original_pk = legacy.pk
    original_code = legacy.subscription_code

    service = VendorService.objects.create(
        legal_entity=entity, vendor=vendor, code="DOMAINS",
        name="Domain Registration", service_type="DOMAIN"
    )
    account = ServiceAccount.objects.create(
        legal_entity=entity, service=service, alias="NetaMate"
    )
    result = json_patch(
        client,
        f"/api/v1/operations/subscriptions/{legacy.pk}/",
        {"service": str(service.pk), "service_account": str(account.pk)},
    )
    assert result.status_code == 200, result.content
    legacy.refresh_from_db()
    assert legacy.pk == original_pk
    assert legacy.subscription_code == original_code
    assert legacy.service_account_id == account.pk

    archived = json_patch(
        client, f"/api/v1/operations/service-accounts/{account.pk}/",
        {"status": "ARCHIVED"}
    )
    assert archived.status_code == 200
    legacy.refresh_from_db()
    assert legacy.service_account_id == account.pk
    assert legacy.payments.count() == 0
