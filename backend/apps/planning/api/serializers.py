from rest_framework import serializers

from apps.accounting.models import Account

from ..models import Budget, BudgetLine, CostCenter, ExpenseAllocation, Product, Project


class CostCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CostCenter
        exclude = ["legal_entity"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        exclude = ["legal_entity"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        exclude = ["legal_entity"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ExpenseAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseAllocation
        fields = [
            "id",
            "expense",
            "cost_center",
            "product",
            "project",
            "amount",
            "base_amount",
            "note",
            "created_at",
        ]
        read_only_fields = fields


class AllocationInputSerializer(serializers.Serializer):
    cost_center = serializers.PrimaryKeyRelatedField(
        queryset=CostCenter.objects.all(),
        required=False,
        allow_null=True,
    )
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        required=False,
        allow_null=True,
    )
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        required=False,
        allow_null=True,
    )
    amount = serializers.DecimalField(max_digits=20, decimal_places=2)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs):
        if not any((attrs.get("cost_center"), attrs.get("product"), attrs.get("project"))):
            raise serializers.ValidationError("At least one planning dimension is required.")
        return attrs


class AllocationReplaceSerializer(serializers.Serializer):
    allocations = AllocationInputSerializer(many=True)


class BudgetSerializer(serializers.ModelSerializer):
    line_count = serializers.IntegerField(source="lines.count", read_only=True)

    class Meta:
        model = Budget
        exclude = ["legal_entity"]
        read_only_fields = ["id", "created_at", "updated_at"]


class BudgetLineSerializer(serializers.ModelSerializer):
    expense_account_name = serializers.CharField(source="expense_account.name", read_only=True)
    cost_center_name = serializers.CharField(source="cost_center.name", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = BudgetLine
        fields = [
            "id",
            "expense_account",
            "expense_account_name",
            "cost_center",
            "cost_center_name",
            "product",
            "product_name",
            "project",
            "project_name",
            "amount",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class BudgetLineCreateSerializer(BudgetLineSerializer):
    expense_account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
    )
