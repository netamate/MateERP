from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from apps.finance.models import FinanceDocument


class FinanceDocumentIntegritySerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, required=False)
    mime_type = serializers.SerializerMethodField()
    size_bytes = serializers.SerializerMethodField()
    checksum_sha256 = serializers.SerializerMethodField()
    uploaded_by_email = serializers.EmailField(source="uploaded_by.email", read_only=True)
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    account_alias = serializers.CharField(source="service_account.alias", read_only=True)
    account_code = serializers.CharField(source="service_account.code", read_only=True)
    subscription_name = serializers.CharField(source="subscription.name", read_only=True)
    subscription_code = serializers.CharField(
        source="subscription.subscription_code",
        read_only=True,
    )
    folder_year = serializers.SerializerMethodField()
    folder_month = serializers.SerializerMethodField()
    content_url = serializers.SerializerMethodField()

    class Meta:
        model = FinanceDocument
        fields = [
            "id",
            "document_type",
            "document_date",
            "reference",
            "file",
            "original_name",
            "standardized_name",
            "vendor",
            "vendor_name",
            "service",
            "service_name",
            "service_account",
            "account_alias",
            "account_code",
            "subscription",
            "subscription_name",
            "subscription_code",
            "expense",
            "income",
            "reimbursement",
            "transfer",
            "founder_funding",
            "uploaded_by_email",
            "mime_type",
            "size_bytes",
            "checksum_sha256",
            "folder_year",
            "folder_month",
            "content_url",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "original_name",
            "standardized_name",
            "uploaded_by_email",
            "vendor_name",
            "service_name",
            "account_alias",
            "account_code",
            "subscription_name",
            "subscription_code",
            "mime_type",
            "size_bytes",
            "checksum_sha256",
            "folder_year",
            "folder_month",
            "content_url",
            "created_at",
        ]

    def validate_file(self, upload):
        if upload.size > 25 * 1024 * 1024:
            raise serializers.ValidationError("Finance documents cannot exceed 25 MB.")
        return upload

    def validate(self, attrs):
        entity = self.context.get("legal_entity")
        if self.instance is None and "file" not in attrs:
            raise serializers.ValidationError({"file": "Choose a document to upload."})

        values = {}
        for field in (
            "vendor",
            "service",
            "service_account",
            "subscription",
            "expense",
            "income",
            "reimbursement",
            "transfer",
            "founder_funding",
        ):
            values[field] = attrs.get(field, getattr(self.instance, field, None))

        if entity:
            for field, record in values.items():
                if record and record.legal_entity_id != entity.id:
                    raise serializers.ValidationError(
                        {field: "This record does not belong to the active legal entity."}
                    )

        finance_targets = [
            values["expense"],
            values["income"],
            values["reimbursement"],
            values["transfer"],
            values["founder_funding"],
        ]
        if len([target for target in finance_targets if target is not None]) > 1:
            raise serializers.ValidationError(
                "Link at most one finance transaction record to a document."
            )

        vendor = values["vendor"]
        service = values["service"]
        account = values["service_account"]
        subscription = values["subscription"]
        if service and vendor and service.vendor_id != vendor.id:
            raise serializers.ValidationError(
                {"service": "Service must belong to the selected vendor."}
            )
        if account and service and account.service_id != service.id:
            raise serializers.ValidationError(
                {"service_account": "Account must belong to the selected service."}
            )
        if account and not service:
            attrs["service"] = account.service
            service = account.service
        if service and not vendor:
            attrs["vendor"] = service.vendor
            vendor = service.vendor
        if subscription:
            if subscription.vendor_id and vendor and subscription.vendor_id != vendor.id:
                raise serializers.ValidationError(
                    {"subscription": "Subscription belongs to a different vendor."}
                )
            if subscription.service_id and service and subscription.service_id != service.id:
                raise serializers.ValidationError(
                    {"subscription": "Subscription belongs to a different service."}
                )
            if (
                subscription.service_account_id
                and account
                and subscription.service_account_id != account.id
            ):
                raise serializers.ValidationError(
                    {"subscription": "Subscription belongs to a different account."}
                )
            if not vendor and subscription.vendor_id:
                attrs["vendor"] = subscription.vendor
            if not service and subscription.service_id:
                attrs["service"] = subscription.service
            if not account and subscription.service_account_id:
                attrs["service_account"] = subscription.service_account
        return attrs

    @staticmethod
    def _metadata(obj):
        try:
            return obj.integrity_metadata
        except (AttributeError, ObjectDoesNotExist):
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

    def get_folder_year(self, obj):
        return obj.document_date.year

    def get_folder_month(self, obj):
        return obj.document_date.month

    def get_content_url(self, obj):
        return f"/api/v1/finance/documents/{obj.id}/content/"
