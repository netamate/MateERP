from rest_framework import serializers

from ..models import ServiceAccount, Subscription, SubscriptionPayment, VendorService


class VendorServiceSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    account_count = serializers.IntegerField(source="accounts.count", read_only=True)

    class Meta:
        model = VendorService
        exclude = ["legal_entity"]
        read_only_fields = ["id", "vendor_name", "account_count", "created_at", "updated_at"]

    def validate(self, attrs):
        entity = self.context.get("legal_entity")
        vendor = attrs.get("vendor", getattr(self.instance, "vendor", None))
        code = attrs.get("code", getattr(self.instance, "code", "")).strip().upper()
        if not vendor or not entity or vendor.legal_entity_id != entity.id:
            raise serializers.ValidationError({"vendor": "Choose a vendor from the active legal entity."})
        if not code:
            raise serializers.ValidationError({"code": "Service code is required."})
        others = VendorService.objects.filter(
            legal_entity=entity, vendor=vendor, code__iexact=code
        )
        if self.instance:
            others = others.exclude(pk=self.instance.pk)
        if others.exists():
            raise serializers.ValidationError({"code": "This vendor already has that service code."})
        attrs["code"] = code
        return attrs


class ServiceAccountSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)
    vendor_id = serializers.UUIDField(source="service.vendor_id", read_only=True)
    vendor_name = serializers.CharField(source="service.vendor.name", read_only=True)
    subscription_count = serializers.IntegerField(source="subscriptions.count", read_only=True)

    class Meta:
        model = ServiceAccount
        exclude = ["legal_entity"]
        read_only_fields = [
            "id", "code", "service_name", "vendor_id", "vendor_name", "subscription_count",
            "created_at", "updated_at",
        ]

    def validate(self, attrs):
        entity = self.context.get("legal_entity")
        service = attrs.get("service", getattr(self.instance, "service", None))
        alias = attrs.get("alias", getattr(self.instance, "alias", "")).strip()
        if not service or not entity or service.legal_entity_id != entity.id:
            raise serializers.ValidationError({"service": "Choose a service from the active legal entity."})
        if not alias:
            raise serializers.ValidationError({"alias": "Account alias is required."})
        existing = ServiceAccount.objects.filter(service=service, alias__iexact=alias)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError(
                {"alias": "An account with this alias already exists for the service."}
            )
        attrs["alias"] = alias
        return attrs


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(source="created_by.email", read_only=True)

    class Meta:
        model = SubscriptionPayment
        exclude = ["legal_entity", "created_by"]
        read_only_fields = ["id", "created_at", "created_by_email"]


class SubscriptionSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    vendor_service_name = serializers.CharField(source="service.name", read_only=True)
    account_alias = serializers.CharField(source="service_account.alias", read_only=True)
    account_code = serializers.CharField(source="service_account.code", read_only=True)
    payments = SubscriptionPaymentSerializer(many=True, read_only=True)
    payment_count = serializers.IntegerField(source="payments.count", read_only=True)

    class Meta:
        model = Subscription
        exclude = ["legal_entity"]
        read_only_fields = [
            "id",
            "subscription_code",
            "created_at",
            "updated_at",
            "vendor_name",
            "vendor_service_name",
            "account_alias",
            "account_code",
            "payments",
            "payment_count",
        ]

    def validate(self, attrs):
        entity = self.context.get("legal_entity")
        vendor = attrs.get("vendor", getattr(self.instance, "vendor", None))
        service = attrs.get("service", getattr(self.instance, "service", None))
        account = attrs.get("service_account", getattr(self.instance, "service_account", None))
        if entity:
            for field, obj in (
                ("vendor", vendor),
                ("service", service),
                ("service_account", account),
            ):
                if obj and obj.legal_entity_id != entity.id:
                    raise serializers.ValidationError(
                        {field: "This record does not belong to the active legal entity."}
                    )
        if service and vendor and service.vendor_id != vendor.pk:
            raise serializers.ValidationError({"service": "Service must belong to this vendor."})
        if account and not service:
            raise serializers.ValidationError({"service_account": "Select a service first."})
        if account and account.service_id != service.pk:
            raise serializers.ValidationError(
                {"service_account": "Account must belong to the selected service."}
            )
        return attrs

    def validate_reminder_days(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Reminder days must be a list.")
        normalized = []
        for item in value:
            if not isinstance(item, int) or isinstance(item, bool) or item < 0 or item > 365:
                raise serializers.ValidationError(
                    "Reminder day offsets must be integers between 0 and 365."
                )
            if item not in normalized:
                normalized.append(item)
        return sorted(normalized, reverse=True)

    def validate_reminder_email_recipients(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Email recipients must be a list.")
        field = serializers.EmailField()
        normalized = []
        for item in value:
            email = field.run_validation(item)
            if email not in normalized:
                normalized.append(email)
        return normalized


class SubscriptionPaymentActionSerializer(serializers.Serializer):
    paid_on = serializers.DateField()
    amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        required=False,
    )
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=255)
    notes = serializers.CharField(required=False, allow_blank=True)


class RenewalQuerySerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end < start:
            raise serializers.ValidationError("end_date cannot be before start_date.")
        return attrs
