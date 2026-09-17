from rest_framework import serializers

from apps.finance.models import FinanceDocument


class FinanceDocumentIntegritySerializer(serializers.ModelSerializer):
    mime_type = serializers.SerializerMethodField()
    size_bytes = serializers.SerializerMethodField()
    checksum_sha256 = serializers.SerializerMethodField()
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

    @staticmethod
    def _metadata(obj):
        try:
            return obj.integrity_metadata
        except (AttributeError, FinanceDocument.integrity_metadata.RelatedObjectDoesNotExist):
            return None

    def get_mime_type(self, obj):
        metadata = self._metadata(obj)
        return metadata.mime_type if metadata else None

    def get_size_bytes(self, obj):
        metadata = self._metadata(obj)
        return metadata.size_bytes if metadata else None

    def get_checksum_sha256(self, obj):
        metadata = self._metadata(obj)
        return metadata.checksum_sha256 if metadata else None
