from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework import serializers

from apps.notifications.crypto import encrypt_secret
from apps.operations.models import BillingMode, Subscription

from ..models import (
    AutomationPolicy,
    AutomationRun,
    VendorAuthType,
    VendorIntegration,
    VendorSyncRun,
)


class VendorIntegrationSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    subscription_name = serializers.CharField(source="subscription.name", read_only=True)
    subscription_code = serializers.CharField(
        source="subscription.subscription_code",
        read_only=True,
    )
    secret = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )
    clear_secret = serializers.BooleanField(write_only=True, required=False, default=False)
    secret_configured = serializers.SerializerMethodField()

    class Meta:
        model = VendorIntegration
        exclude = [
            "organization",
            "legal_entity",
            "secret_encrypted",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "last_test_at",
            "last_test_status",
            "last_test_error",
            "last_sync_at",
            "last_sync_status",
            "last_sync_error",
            "created_at",
            "updated_at",
            "vendor_name",
            "subscription_name",
            "subscription_code",
            "secret_configured",
        ]

    def get_secret_configured(self, obj):
        return bool(obj.secret_encrypted)

    def validate_endpoint_url(self, value):
        parsed = urlparse(value)
        if parsed.scheme.lower() != "https":
            raise serializers.ValidationError("Vendor API endpoint must use HTTPS.")
        if not parsed.hostname or parsed.username or parsed.password:
            raise serializers.ValidationError("Vendor API endpoint is invalid.")
        return value

    def validate(self, attrs):
        entity = self.context["legal_entity"]
        vendor = attrs.get("vendor", getattr(self.instance, "vendor", None))
        subscription = attrs.get(
            "subscription",
            getattr(self.instance, "subscription", None),
        )
        auth_type = attrs.get(
            "auth_type",
            getattr(self.instance, "auth_type", VendorAuthType.NONE),
        )
        secret = attrs.pop("secret", None)
        clear_secret = attrs.pop("clear_secret", False)

        if vendor and vendor.legal_entity_id != entity.id:
            raise serializers.ValidationError({"vendor": "Vendor belongs to another legal entity."})
        if subscription:
            if subscription.legal_entity_id != entity.id:
                raise serializers.ValidationError(
                    {"subscription": "Subscription belongs to another legal entity."}
                )
            if subscription.billing_mode != BillingMode.PAYG:
                raise serializers.ValidationError(
                    {"subscription": "Vendor integrations require a PAYG subscription."}
                )
            if subscription.vendor_id and vendor and subscription.vendor_id != vendor.id:
                raise serializers.ValidationError(
                    {"vendor": "Vendor must match the subscription vendor."}
                )

        existing_secret = bool(getattr(self.instance, "secret_encrypted", ""))
        needs_secret = auth_type != VendorAuthType.NONE
        if needs_secret and clear_secret:
            raise serializers.ValidationError(
                {"secret": "Authenticated connectors cannot clear their secret."}
            )
        if needs_secret and not secret and not existing_secret:
            raise serializers.ValidationError(
                {"secret": "This authentication method requires a secret."}
            )
        attrs["_secret_value"] = secret
        attrs["_clear_secret"] = clear_secret
        return attrs

    def create(self, validated_data):
        secret = validated_data.pop("_secret_value", None)
        validated_data.pop("_clear_secret", False)
        return VendorIntegration.objects.create(
            organization=self.context["organization"],
            legal_entity=self.context["legal_entity"],
            created_by=self.context.get("actor"),
            updated_by=self.context.get("actor"),
            secret_encrypted=encrypt_secret(secret or ""),
            **validated_data,
        )

    def update(self, instance, validated_data):
        secret = validated_data.pop("_secret_value", None)
        clear_secret = validated_data.pop("_clear_secret", False)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if secret:
            instance.secret_encrypted = encrypt_secret(secret)
        elif clear_secret:
            instance.secret_encrypted = ""
        instance.updated_by = self.context.get("actor")
        instance.save()
        return instance


class VendorIntegrationTestSerializer(serializers.Serializer):
    integration_id = serializers.UUIDField(required=False, allow_null=True)
    subscription = serializers.PrimaryKeyRelatedField(queryset=Subscription.objects.all())
    endpoint_url = serializers.URLField(max_length=1000)
    auth_type = serializers.ChoiceField(choices=VendorAuthType.choices)
    auth_username = serializers.CharField(required=False, allow_blank=True, default="")
    secret = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
        default="",
    )
    api_key_header = serializers.CharField(required=False, allow_blank=True, default="X-API-Key")
    custom_headers = serializers.JSONField(required=False, default=dict)
    cost_json_path = serializers.CharField(max_length=255)
    usage_quantity_json_path = serializers.CharField(required=False, allow_blank=True, default="")
    currency_json_path = serializers.CharField(required=False, allow_blank=True, default="")
    usage_unit_json_path = serializers.CharField(required=False, allow_blank=True, default="")
    timeout_seconds = serializers.IntegerField(min_value=3, max_value=60, default=15)

    def validate_endpoint_url(self, value):
        parsed = urlparse(value)
        if parsed.scheme.lower() != "https":
            raise serializers.ValidationError("Vendor API endpoint must use HTTPS.")
        if not parsed.hostname or parsed.username or parsed.password:
            raise serializers.ValidationError("Vendor API endpoint is invalid.")
        return value

    def validate_subscription(self, value):
        entity = self.context["legal_entity"]
        if value.legal_entity_id != entity.id:
            raise serializers.ValidationError("Subscription belongs to another legal entity.")
        if value.billing_mode != BillingMode.PAYG:
            raise serializers.ValidationError("Vendor integrations require a PAYG subscription.")
        return value

    def validate_api_key_header(self, value):
        header = value.strip()
        if not header:
            return header
        if not header.replace("-", "").isalnum():
            raise serializers.ValidationError("API key header contains invalid characters.")
        if header.lower() in {"authorization", "cookie", "host", "content-length"}:
            raise serializers.ValidationError("Use a dedicated API key header.")
        return header

    def validate_custom_headers(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Custom headers must be a JSON object.")
        protected = {"authorization", "cookie", "host", "content-length"}
        if any(str(key).lower() in protected for key in value):
            raise serializers.ValidationError("Protected HTTP headers cannot be overridden.")
        return {str(key): str(item) for key, item in value.items()}

    def validate(self, attrs):
        auth_type = attrs.get("auth_type", VendorAuthType.NONE)
        secret = attrs.get("secret", "")
        integration_id = attrs.get("integration_id")
        if auth_type != VendorAuthType.NONE and not secret and not integration_id:
            raise serializers.ValidationError(
                {"secret": "This authentication method requires a secret."}
            )
        if auth_type == VendorAuthType.BASIC and not attrs.get("auth_username", "").strip():
            raise serializers.ValidationError(
                {"auth_username": "Basic authentication requires a username."}
            )
        return attrs


class VendorSyncRunSerializer(serializers.ModelSerializer):
    integration_name = serializers.CharField(source="integration.name", read_only=True)
    vendor_name = serializers.CharField(source="integration.vendor.name", read_only=True)
    subscription_name = serializers.CharField(
        source="integration.subscription.name",
        read_only=True,
    )

    class Meta:
        model = VendorSyncRun
        fields = [
            "id",
            "integration",
            "integration_name",
            "vendor_name",
            "subscription_name",
            "trigger",
            "status",
            "http_status",
            "billing_period",
            "cost_amount",
            "usage_quantity",
            "currency",
            "usage_unit",
            "error",
            "started_at",
            "finished_at",
        ]
        read_only_fields = fields


class AutomationPolicySerializer(serializers.ModelSerializer):
    legal_entity_name = serializers.CharField(
        source="legal_entity.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = AutomationPolicy
        exclude = ["organization", "created_by", "updated_by"]
        read_only_fields = [
            "id",
            "last_run_at",
            "last_status",
            "last_summary",
            "last_error",
            "created_at",
            "updated_at",
            "legal_entity_name",
        ]

    def validate_schedule_timezone(self, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise serializers.ValidationError("Use a valid IANA timezone.") from exc
        return value

    def validate(self, attrs):
        organization = self.context["organization"]
        entity = attrs.get("legal_entity", getattr(self.instance, "legal_entity", None))
        if entity and entity.organization_id != organization.id:
            raise serializers.ValidationError(
                {"legal_entity": "Choose a legal entity from this organization."}
            )
        hour = attrs.get("schedule_hour", getattr(self.instance, "schedule_hour", 0))
        if hour > 23:
            raise serializers.ValidationError(
                {"schedule_hour": "Schedule hour must be between 0 and 23."}
            )
        return attrs


class AutomationRunSerializer(serializers.ModelSerializer):
    policy_name = serializers.CharField(source="policy.name", read_only=True)
    policy_kind = serializers.CharField(source="policy.kind", read_only=True)

    class Meta:
        model = AutomationRun
        fields = [
            "id",
            "policy",
            "policy_name",
            "policy_kind",
            "trigger",
            "status",
            "summary",
            "error",
            "started_at",
            "finished_at",
        ]
        read_only_fields = fields


class AutomationOverviewSerializer(serializers.Serializer):
    active_integrations = serializers.IntegerField()
    failed_integrations = serializers.IntegerField()
    enabled_policies = serializers.IntegerField()
    failed_runs_24h = serializers.IntegerField()
    last_vendor_sync_at = serializers.DateTimeField(allow_null=True)
