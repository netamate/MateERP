from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings

from apps.finance.models import Vendor
from apps.identity.models import Membership, Role, User
from apps.identity.services import create_organization_with_owner
from apps.operations.models import ServiceAccount, Subscription, VendorService


def signed_in_owner(email: str, organization_name: str):
    owner = User.objects.create_user(email=email, password="test-pass-123")
    organization, entity, _ = create_organization_with_owner(
        owner=owner,
        name=organization_name,
        base_currency="USD",
    )
    client = Client()
    client.force_login(owner)
    session = client.session
    session["active_organization_id"] = str(organization.id)
    session["active_legal_entity_id"] = str(entity.id)
    session.save()
    return client, entity


def pdf(name="invoice.pdf", marker=b"one"):
    return SimpleUploadedFile(
        name,
        b"%PDF-1.4\n" + marker + b"\n%%EOF",
        content_type="application/pdf",
    )


@pytest.mark.django_db
def test_smart_upload_generates_stable_name_and_virtual_folder(tmp_path):
    client, entity = signed_in_owner("library-owner@example.com", "Library Org")
    vendor = Vendor.objects.create(legal_entity=entity, code="OPENAI", name="OpenAI")
    service = VendorService.objects.create(
        legal_entity=entity,
        vendor=vendor,
        code="CHATGPT",
        name="ChatGPT",
        service_type="AI",
    )
    account = ServiceAccount.objects.create(
        legal_entity=entity,
        service=service,
        alias="Rizwan-01",
    )
    subscription = Subscription.objects.create(
        legal_entity=entity,
        vendor=vendor,
        service=service,
        service_account=account,
        name="ChatGPT Plus",
        service_type="AI",
        amount="20.00",
    )

    with override_settings(MEDIA_ROOT=tmp_path):
        response = client.post(
            "/api/v1/finance/documents/",
            data={
                "document_type": "INVOICE",
                "document_date": "2026-10-07",
                "reference": "INV-42",
                "subscription": str(subscription.id),
                "file": pdf(),
            },
        )

    assert response.status_code == 201, response.content
    body = response.json()
    assert body["original_name"] == "invoice.pdf"
    assert body["vendor_name"] == "OpenAI"
    assert body["service_name"] == "ChatGPT"
    assert body["account_alias"] == "Rizwan-01"
    assert body["subscription_code"] == subscription.subscription_code
    assert body["folder_year"] == 2026
    assert body["folder_month"] == 10
    assert body["content_url"].endswith(f"/{body['id']}/content/")
    assert "file" not in body
    expected = (
        f"OpenAI_ChatGPT_Rizwan-01_{subscription.subscription_code}_INVOICE_2026-10-07_INV-42.pdf"
    )
    assert body["standardized_name"] == expected
    stored = subscription.documents.get()
    assert stored.file.name.startswith("finance/2026/10/")
    assert stored.file.name.endswith(expected)


@pytest.mark.django_db
def test_duplicate_file_is_rejected_with_existing_document_reference(tmp_path):
    client, entity = signed_in_owner("duplicate-owner@example.com", "Duplicate Org")
    vendor = Vendor.objects.create(legal_entity=entity, code="VENDOR", name="Vendor")
    with override_settings(MEDIA_ROOT=tmp_path):
        first = client.post(
            "/api/v1/finance/documents/",
            data={
                "document_type": "RECEIPT",
                "document_date": "2026-10-07",
                "vendor": str(vendor.id),
                "file": pdf(marker=b"same-document"),
            },
        )
        second = client.post(
            "/api/v1/finance/documents/",
            data={
                "document_type": "RECEIPT",
                "document_date": "2026-10-08",
                "vendor": str(vendor.id),
                "file": pdf(name="copy.pdf", marker=b"same-document"),
            },
        )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["duplicate_document_id"] == first.json()["id"]


@pytest.mark.django_db
def test_unassigned_document_can_be_uploaded_and_filtered(tmp_path):
    client, _ = signed_in_owner("unassigned-owner@example.com", "Unassigned Org")
    with override_settings(MEDIA_ROOT=tmp_path):
        response = client.post(
            "/api/v1/finance/documents/",
            data={
                "document_type": "STATEMENT",
                "document_date": "2026-01-15",
                "file": pdf(marker=b"unassigned"),
            },
        )
        filtered = client.get("/api/v1/finance/documents/?year=2026&month=1&unassigned=1")

    assert response.status_code == 201, response.content
    assert response.json()["standardized_name"].startswith("Unassigned_STATEMENT_2026-01-15_")
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()] == [response.json()["id"]]


@pytest.mark.django_db
def test_private_content_stream_supports_preview_and_both_download_names(tmp_path):
    client, entity = signed_in_owner("stream-owner@example.com", "Stream Org")
    vendor = Vendor.objects.create(legal_entity=entity, code="NC", name="Namecheap")
    with override_settings(MEDIA_ROOT=tmp_path):
        created = client.post(
            "/api/v1/finance/documents/",
            data={
                "document_type": "INVOICE",
                "document_date": "2026-10-07",
                "reference": "NC-99",
                "vendor": str(vendor.id),
                "file": pdf("namecheap-original.pdf", marker=b"stream-me"),
            },
        ).json()
        inline = client.get(created["content_url"])
        standard = client.get(created["content_url"] + "?disposition=attachment&name=standard")
        original = client.get(created["content_url"] + "?disposition=attachment&name=original")

    assert inline.status_code == 200
    assert inline["Cache-Control"] == "private, no-store"
    assert inline["X-Frame-Options"] == "SAMEORIGIN"
    assert inline["Content-Type"] == "application/pdf"
    assert "inline" in inline["Content-Disposition"]
    assert b"stream-me" in b"".join(inline.streaming_content)
    assert created["standardized_name"] in standard["Content-Disposition"]
    assert "namecheap-original.pdf" in original["Content-Disposition"]


@pytest.mark.django_db
def test_metadata_edit_rebuilds_standard_name_without_replacing_original(tmp_path):
    client, entity = signed_in_owner("edit-owner@example.com", "Edit Org")
    vendor = Vendor.objects.create(legal_entity=entity, code="AZ", name="Microsoft")
    with override_settings(MEDIA_ROOT=tmp_path):
        created = client.post(
            "/api/v1/finance/documents/",
            data={
                "document_type": "INVOICE",
                "document_date": "2026-09-30",
                "vendor": str(vendor.id),
                "reference": "OLD",
                "file": pdf("azure.pdf", marker=b"edit"),
            },
        ).json()
        updated = client.patch(
            f"/api/v1/finance/documents/{created['id']}/",
            data={
                "document_date": "2026-10-01",
                "reference": "AZ-100",
                "document_type": "PAYMENT_CONFIRMATION",
            },
            content_type="application/json",
        )

    assert updated.status_code == 200, updated.content
    body = updated.json()
    assert body["original_name"] == "azure.pdf"
    assert body["document_date"] == "2026-10-01"
    assert body["standardized_name"].endswith("PAYMENT_CONFIRMATION_2026-10-01_AZ-100.pdf")


@pytest.mark.django_db
def test_cross_entity_document_association_and_invalid_file_are_blocked(tmp_path):
    first, entity1 = signed_in_owner("docs-first@example.com", "Docs First")
    second, entity2 = signed_in_owner("docs-second@example.com", "Docs Second")
    foreign_vendor = Vendor.objects.create(
        legal_entity=entity2,
        code="FOREIGN",
        name="Foreign Vendor",
    )

    with override_settings(MEDIA_ROOT=tmp_path):
        cross = first.post(
            "/api/v1/finance/documents/",
            data={
                "document_type": "INVOICE",
                "document_date": str(date(2026, 10, 7)),
                "vendor": str(foreign_vendor.id),
                "file": pdf(marker=b"cross"),
            },
        )
        invalid = first.post(
            "/api/v1/finance/documents/",
            data={
                "document_type": "OTHER",
                "document_date": "2026-10-07",
                "file": SimpleUploadedFile(
                    "payload.txt",
                    b"not a supported finance document",
                    content_type="text/plain",
                ),
            },
        )

    assert cross.status_code == 400
    assert invalid.status_code == 400
    assert entity1.finance_documents.count() == 0


@pytest.mark.django_db
def test_payslip_hidden_from_regular_finance_viewer(tmp_path):
    owner, entity = signed_in_owner("payroll-owner@example.com", "Payroll Org")
    member_user = User.objects.create_user(
        email="payroll-member@example.com", password="test-pass-123"
    )
    Membership.objects.create(
        organization=entity.organization,
        user=member_user,
        role=Role.MEMBER,
        all_legal_entities=True,
    )
    member = Client()
    member.force_login(member_user)
    member_session = member.session
    member_session["active_organization_id"] = str(entity.organization_id)
    member_session["active_legal_entity_id"] = str(entity.id)
    member_session.save()

    with override_settings(MEDIA_ROOT=tmp_path):
        created = owner.post(
            "/api/v1/finance/documents/",
            data={
                "document_type": "PAYSLIP",
                "document_date": "2026-10-07",
                "file": pdf(name="payroll.pdf", marker=b"confidential"),
            },
        )
        assert created.status_code == 201, created.content
        payslip_id = created.json()["id"]

        assert member.get("/api/v1/finance/documents/").json() == []
        assert member.get(f"/api/v1/finance/documents/{payslip_id}/").status_code == 403
        assert member.get(f"/api/v1/finance/documents/{payslip_id}/content/").status_code == 403
        denied_upload = member.post(
            "/api/v1/finance/documents/",
            data={
                "document_type": "PAYSLIP",
                "document_date": "2026-10-07",
                "file": pdf(name="unauthorized.pdf", marker=b"unauthorized"),
            },
        )
        assert denied_upload.status_code == 403
