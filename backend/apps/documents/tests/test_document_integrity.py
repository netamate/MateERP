import hashlib

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.documents.services import create_finance_document_with_metadata
from apps.finance.models import Vendor
from apps.identity.models import User
from apps.identity.services import create_organization_with_owner


@pytest.mark.django_db
def test_finance_document_stores_sha256_mime_type_and_size(tmp_path):
    owner = User.objects.create_user(email="docs-owner@example.com", password="test-pass-123")
    _, entity, _ = create_organization_with_owner(
        owner=owner,
        name="Document Test",
        base_currency="USD",
    )
    vendor = Vendor.objects.create(legal_entity=entity, code="DOC", name="Document Vendor")
    payload = b"mateerp-document-integrity"
    upload = SimpleUploadedFile("invoice.pdf", payload, content_type="application/pdf")

    with override_settings(MEDIA_ROOT=tmp_path):
        document = create_finance_document_with_metadata(
            legal_entity=entity,
            uploaded_by=owner,
            validated_data={
                "document_type": "INVOICE",
                "file": upload,
                "vendor": vendor,
            },
        )

    metadata = document.integrity_metadata
    assert metadata.mime_type == "application/pdf"
    assert metadata.size_bytes == len(payload)
    assert metadata.checksum_sha256 == hashlib.sha256(payload).hexdigest()
