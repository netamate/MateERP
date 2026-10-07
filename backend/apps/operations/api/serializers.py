from rest_framework import serializers

from ..models import Subscription, SubscriptionPayment


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(source="created_by.email", read_only=True)

    class Meta:
        model = SubscriptionPayment
        exclude = ["legal_entity", "created_by"]
        read_only_fields = ["id", "created_at", "created_by_email"]


class SubscriptionSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    payments = SubscriptionPaymentSerializer(many=True, read_only=True)
    payment_count = serializers.IntegerField(source="payments.count", read_only=True)

    class Meta:
        model = Subscription
        exclude = ["legal_entity"]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "vendor_name",
            "payments",
            "payment_count",
        ]

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
