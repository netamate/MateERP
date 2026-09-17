from rest_framework import serializers

from apps.finance.models import FinanceDocument


class FinanceDocumentIntegritySerializer(serializers.ModelSerializer):
    mime_type = serializers.CharField(source="integrity_metadata.mime_type", read_only=True)
    size_bytes = serializers.IntegerField(source="integrity_metadata.size_bytes", read_only=True)
    checksum_sha256 = serializers.CharField(
        source="integrity_metadata.checksum_sha256",
        read_only=True,
    )
    uploaded_by_email = serializers.EmailField(source="uploaded_by.email", read_only=True)

    class Meta:
        model = FinanceDocument
        fields = [
            "id",
            "document_type",
            "file",
            "original_name",
            "vendor",
            "expense",
            "income",
            "reimbursement",
            "transfer",
            "founder_funding",
            "uploaded_by_email",
            "mime_type",
            "size_bytes",
            "checksum_sha256",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "original_name",
            "uploaded_by_email",
            "mime_type",
            "size_bytes",
            "checksum_sha256",
            "created_at",
        ]
