from rest_framework import serializers

from apps.accounting.models import (
    Account,
    ExchangeRate,
    FiscalPeriod,
    JournalEntry,
    JournalLine,
    TaxCode,
)


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = [
            "id",
            "legal_entity_id",
            "code",
            "name",
            "account_type",
            "normal_balance",
            "parent_id",
            "system_code",
            "is_control",
            "is_active",
        ]
        read_only_fields = ["legal_entity_id"]


class FiscalPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = FiscalPeriod
        fields = ["id", "legal_entity_id", "name", "start_date", "end_date", "status"]
        read_only_fields = ["legal_entity_id", "status"]


class TaxCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxCode
        fields = [
            "id",
            "legal_entity_id",
            "code",
            "name",
            "rate",
            "input_account_id",
            "output_account_id",
            "is_active",
        ]
        read_only_fields = ["legal_entity_id"]


class ExchangeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExchangeRate
        fields = [
            "id",
            "legal_entity_id",
            "rate_date",
            "from_currency",
            "to_currency",
            "rate",
            "source",
        ]
        read_only_fields = ["legal_entity_id"]


class JournalLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalLine
        fields = [
            "id",
            "account_id",
            "description",
            "debit",
            "credit",
            "currency",
            "fx_rate",
            "base_debit",
            "base_credit",
            "tax_code_id",
        ]
        read_only_fields = ["base_debit", "base_credit"]


class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalLineSerializer(many=True, read_only=True)

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "legal_entity_id",
            "number",
            "entry_date",
            "memo",
            "status",
            "source_type",
            "source_id",
            "reversal_of_id",
            "posted_at",
            "lines",
        ]


class JournalCreateSerializer(serializers.Serializer):
    entry_date = serializers.DateField()
    memo = serializers.CharField(required=False, allow_blank=True, default="")
    source_type = serializers.CharField(required=False, default="MANUAL")
    source_id = serializers.CharField(required=False, allow_blank=True, default="")
    lines = JournalLineSerializer(many=True)


class JournalReverseSerializer(serializers.Serializer):
    reversal_date = serializers.DateField()
    memo = serializers.CharField(required=False, allow_blank=True, default="")


class PeriodCloseSerializer(serializers.Serializer):
    hard_close = serializers.BooleanField(default=False)
