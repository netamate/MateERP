import hashlib
import re
from pathlib import Path

from django.db import transaction

from apps.finance.models import FinanceDocument

from .models import FinanceDocumentMetadata

ALLOWED_DOCUMENT_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024


class DuplicateDocumentError(Exception):
    def __init__(self, document):
        self.document = document
        super().__init__("This exact document is already stored in the library.")


def _detected_mime(header: bytes) -> str:
    if header.startswith(b"%PDF-"):
        return "application/pdf"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return "application/octet-stream"


def inspect_upload(upload):
    hasher = hashlib.sha256()
    size_bytes = 0
    header = b""
    for chunk in upload.chunks():
        if not header:
            header = bytes(chunk[:16])
        hasher.update(chunk)
        size_bytes += len(chunk)
        if size_bytes > MAX_DOCUMENT_BYTES:
            raise ValueError("Finance documents cannot exceed 25 MB.")
    if hasattr(upload, "seek"):
        upload.seek(0)
    mime_type = _detected_mime(header)
    if mime_type not in ALLOWED_DOCUMENT_TYPES:
        raise ValueError("Upload a PDF, PNG, or JPEG financial document.")
    return {
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "checksum_sha256": hasher.hexdigest(),
    }


def _token(value, fallback=""):
    text = str(value or "").strip()
    if not text:
        return fallback
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^A-Za-z0-9.-]+", "-", text)
    return (re.sub(r"-{2,}", "-", text).strip("-._") or fallback)[:40]


def _extension(original_name: str, mime_type: str) -> str:
    suffix = Path(original_name).suffix.lower()
    allowed_suffixes = {".pdf", ".png", ".jpg", ".jpeg"}
    if suffix in allowed_suffixes:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ALLOWED_DOCUMENT_TYPES[mime_type]


def hydrate_document_hierarchy(document: FinanceDocument) -> None:
    if document.subscription_id:
        if not document.vendor_id:
            document.vendor = document.subscription.vendor
        if not document.service_id:
            document.service = document.subscription.service
        if not document.service_account_id:
            document.service_account = document.subscription.service_account
    if document.service_account_id:
        if not document.service_id:
            document.service = document.service_account.service
        if not document.vendor_id:
            document.vendor = document.service_account.service.vendor
    if document.service_id and not document.vendor_id:
        document.vendor = document.service.vendor


def standardized_document_name(document: FinanceDocument, *, mime_type: str) -> str:
    hydrate_document_hierarchy(document)
    parts = [_token(document.vendor.name if document.vendor_id else None, "Unassigned")]
    if document.service_id:
        parts.append(_token(document.service.name, "Service"))
    if document.service_account_id:
        parts.append(_token(document.service_account.alias, "Account"))
    if document.subscription_id:
        parts.append(_token(document.subscription.subscription_code, "Subscription"))
    parts.extend(
        [
            document.document_type,
            document.document_date.isoformat(),
            _token(document.reference, document.id.hex[:8].upper()),
        ]
    )
    name = "_".join(part for part in parts if part) + _extension(
        document.original_name, mime_type
    )
    return name[:255]


def _unique_standardized_name(document: FinanceDocument, *, mime_type: str) -> str:
    name = standardized_document_name(document, mime_type=mime_type)
    collision = FinanceDocument.objects.filter(
        legal_entity=document.legal_entity,
        standardized_name=name,
    ).exclude(pk=document.pk)
    if collision.exists():
        stem, extension = name.rsplit(".", 1)
        unique_suffix = f"_{document.id.hex[:8].upper()}"
        name = f"{stem[: 254 - len(extension) - len(unique_suffix)]}{unique_suffix}.{extension}"
    return name


def _duplicate_for(*, legal_entity, checksum_sha256: str):
    metadata = (
        FinanceDocumentMetadata.objects.filter(
            checksum_sha256=checksum_sha256,
            document__legal_entity=legal_entity,
        )
        .select_related("document")
        .first()
    )
    return metadata.document if metadata else None


@transaction.atomic
def create_finance_document_with_metadata(
    *,
    legal_entity,
    uploaded_by,
    validated_data,
):
    data = dict(validated_data)
    upload = data.pop("file")
    integrity = inspect_upload(upload)
    duplicate = _duplicate_for(
        legal_entity=legal_entity,
        checksum_sha256=integrity["checksum_sha256"],
    )
    if duplicate:
        raise DuplicateDocumentError(duplicate)

    original_name = getattr(upload, "name", "finance-document") or "finance-document"
    document = FinanceDocument(
        legal_entity=legal_entity,
        uploaded_by=uploaded_by,
        original_name=original_name,
        **data,
    )
    hydrate_document_hierarchy(document)
    document.standardized_name = _unique_standardized_name(
        document,
        mime_type=integrity["mime_type"],
    )
    upload.name = document.standardized_name
    document.file = upload
    document.save()
    FinanceDocumentMetadata.objects.create(document=document, **integrity)
    return document


@transaction.atomic
def update_finance_document_metadata(*, document, validated_data):
    immutable = {"file", "original_name"}
    for field, value in validated_data.items():
        if field not in immutable:
            setattr(document, field, value)
    hydrate_document_hierarchy(document)
    metadata = document.integrity_metadata
    document.standardized_name = _unique_standardized_name(
        document,
        mime_type=metadata.mime_type,
    )
    document.save()
    return document
