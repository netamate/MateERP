from rest_framework import serializers

from apps.finance.models import FinancialAccount

from ..models import AccountReconciliation
from ..selectors import reconciliation_summary


class AccountReconciliationSerializer(serializers.ModelSerializer):
    financial_account_name = serializers.CharField(source="financial_account.name", read_only=True)
    currency = serializers.CharField(source="financial_account.currency", read_only=True)
    summary = serializers.SerializerMethodField()

    class Meta:
        model = AccountReconciliation
        exclude = ["legal_entity", "created_by"]
        read_only_fields = [
            "id",
            "status",
            "completed_by",
            "completed_at",
            "created_at",
            "updated_at",
        ]

    def get_summary(self, obj):
        return reconciliation_summary(obj)


class ReconciliationCreateSerializer(serializers.Serializer):
    financial_account = serializers.PrimaryKeyRelatedField(
        queryset=FinancialAccount.objects.all()
    )
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    statement_ending_balance = serializers.DecimalField(max_digits=20, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError("end_date cannot be before start_date.")
        return attrs


class ReconciliationItemsSerializer(serializers.Serializer):
    journal_line_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=True,
    )
