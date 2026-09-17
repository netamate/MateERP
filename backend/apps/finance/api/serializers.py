from rest_framework import serializers

from apps.identity.models import User

from ..models import (
    ApprovalAction,
    Expense,
    ExpensePayment,
    FinanceDocument,
    FinancialAccount,
    FounderFunding,
    Income,
    Reimbursement,
    ReimbursementPayment,
    Transfer,
    Vendor,
)


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        exclude = ["legal_entity"]
        read_only_fields = ["id", "created_at", "updated_at"]


class FinancialAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialAccount
        exclude = ["legal_entity"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ExpensePaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpensePayment
        exclude = ["legal_entity", "created_by"]
        read_only_fields = ["id", "base_amount", "journal_entry", "created_at"]


class ExpenseSerializer(serializers.ModelSerializer):
    payments = ExpensePaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Expense
        exclude = ["legal_entity", "created_by"]
        read_only_fields = [
            "id",
            "status",
            "journal_entry",
            "approved_by",
            "approved_at",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]


class IncomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Income
        exclude = ["legal_entity", "created_by"]
        read_only_fields = ["id", "status", "journal_entry", "created_at"]


class TransferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transfer
        exclude = ["legal_entity", "created_by"]
        read_only_fields = ["id", "status", "journal_entry", "created_at"]


class FounderFundingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FounderFunding
        exclude = ["legal_entity", "created_by"]
        read_only_fields = ["id", "status", "journal_entry", "created_at"]


class ReimbursementPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReimbursementPayment
        exclude = ["legal_entity", "created_by"]
        read_only_fields = ["id", "base_amount", "journal_entry", "created_at"]


class ReimbursementSerializer(serializers.ModelSerializer):
    payments = ReimbursementPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Reimbursement
        exclude = ["legal_entity", "created_by"]
        read_only_fields = [
            "id",
            "status",
            "journal_entry",
            "approved_by",
            "approved_at",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]


class FinanceDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceDocument
        exclude = ["legal_entity", "uploaded_by"]
        read_only_fields = ["id", "original_name", "created_at"]


class ApprovalActionSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True)

    class Meta:
        model = ApprovalAction
        fields = [
            "id",
            "object_type",
            "object_id",
            "action",
            "actor",
            "actor_email",
            "comment",
            "created_at",
        ]
        read_only_fields = fields


class WorkflowActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["submit", "approve", "reject"])
    comment = serializers.CharField(required=False, allow_blank=True, max_length=255)


class PaymentCreateSerializer(serializers.Serializer):
    financial_account = serializers.PrimaryKeyRelatedField(queryset=FinancialAccount.objects.all())
    payment_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=20, decimal_places=2)
    currency = serializers.CharField(max_length=3)
    fx_rate = serializers.DecimalField(max_digits=20, decimal_places=10)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=120)


class UserReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "display_name"]
        read_only_fields = fields
