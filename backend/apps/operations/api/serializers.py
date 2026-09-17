from rest_framework import serializers

from ..models import Domain, DomainRenewal, InfrastructureAsset, Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    cost_center_name = serializers.CharField(source="cost_center.name", read_only=True)

    class Meta:
        model = Subscription
        exclude = ["legal_entity"]
        read_only_fields = ["id", "created_at", "updated_at"]


class DomainSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    renewal_count = serializers.IntegerField(source="renewal_history.count", read_only=True)

    class Meta:
        model = Domain
        exclude = ["legal_entity"]
        read_only_fields = ["id", "created_at", "updated_at"]


class InfrastructureAssetSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    cost_center_name = serializers.CharField(source="cost_center.name", read_only=True)

    class Meta:
        model = InfrastructureAsset
        exclude = ["legal_entity"]
        read_only_fields = ["id", "created_at", "updated_at"]


class DomainRenewalSerializer(serializers.ModelSerializer):
    class Meta:
        model = DomainRenewal
        exclude = ["legal_entity", "created_by"]
        read_only_fields = ["id", "created_at"]


class DomainRenewActionSerializer(serializers.Serializer):
    renewed_on = serializers.DateField()
    new_expiry_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=20, decimal_places=2)
    currency = serializers.CharField(max_length=3)
    fx_rate = serializers.DecimalField(max_digits=20, decimal_places=10, default="1")
    notes = serializers.CharField(required=False, allow_blank=True, max_length=255)
    generate_expense = serializers.BooleanField(default=False)


class RenewalQuerySerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end < start:
            raise serializers.ValidationError("end_date cannot be before start_date.")
        return attrs
