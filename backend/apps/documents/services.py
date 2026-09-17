import hashlib
import mimetypes

from django.db import transaction

from apps.finance.models import FinanceDocument

from .models import FinanceDocumentMetadata


def inspect_upload(upload):
    hasher = hashlib.sha256()
    size_bytes = 0
    for chunk in upload.chunks():
        hasher.update(chunk)
        size_bytes += len(chunk)
    if hasattr(upload, "seek"):
        upload.seek(0)
    mime_type = getattr(upload, "content_type", "") or ""
    if not mime_type:
        mime_type = (
            mimetypes.guess_type(getattr(upload, "name", ""))[0] or "application/octet-stream"
        )
    return {
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "checksum_sha256": hasher.hexdigest(),
    }


@transaction.atomic
def create_finance_document_with_metadata(
    *,
    legal_entity,
    uploaded_by,
    validated_data,
):
    upload = validated_data["file"]
    integrity = inspect_upload(upload)
    document = FinanceDocument.objects.create(
        legal_entity=legal_entity,
        uploaded_by=uploaded_by,
        original_name=getattr(upload, "name", "finance-document"),
        **validated_data,
    )
    FinanceDocumentMetadata.objects.create(document=document, **integrity)
    return document
