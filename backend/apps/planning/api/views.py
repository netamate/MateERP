from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.finance.models import Expense
from apps.identity.policy import Permission, has_permission
from apps.identity.services import set_active_context

from ..models import Budget, CostCenter, Product, Project
from ..selectors import budget_actuals
from ..services import audit_planning_change, replace_expense_allocations
from .serializers import (
    AllocationReplaceSerializer,
    BudgetLineCreateSerializer,
    BudgetLineSerializer,
    BudgetSerializer,
    CostCenterSerializer,
    ExpenseAllocationSerializer,
    ProductSerializer,
    ProjectSerializer,
)


def _context(request):
    organization_id = request.session.get("active_organization_id")
    legal_entity_id = request.session.get("active_legal_entity_id")
    if not organization_id or not legal_entity_id:
        raise ValidationError("Select an active organization and legal entity first.")
    return set_active_context(
        user=request.user,
        organization_id=organization_id,
        legal_entity_id=legal_entity_id,
    )


def _require_view(context):
    if not has_permission(context.membership, Permission.VIEW_PLANNING):
        raise PermissionDenied("You do not have permission to view planning data.")


def _require_manage(context):
    if not has_permission(context.membership, Permission.MANAGE_PLANNING):
        raise PermissionDenied("You do not have permission to manage planning data.")


def _get_scoped(model, context, object_id):
    obj = model.objects.filter(id=object_id, legal_entity=context.legal_entity).first()
    if obj is None:
        raise ValidationError("Planning record does not exist in the active legal entity.")
    return obj


def _save_master(request, context, serializer, *, object_type: str, action: str):
    serializer.is_valid(raise_exception=True)
    obj = serializer.save(legal_entity=context.legal_entity)
    audit_planning_change(
        membership=context.membership,
        legal_entity=context.legal_entity,
        action=action,
        object_type=object_type,
        object_id=obj.id,
        state=serializer.__class__(obj).data,
        request=request,
    )
    return obj


class CostCenterListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = CostCenter.objects.filter(legal_entity=context.legal_entity)
        return Response(CostCenterSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        _require_manage(context)
        serializer = CostCenterSerializer(data=request.data)
        obj = _save_master(
            request,
            context,
            serializer,
            object_type="CostCenter",
            action="planning.cost_center_created",
        )
        return Response(CostCenterSerializer(obj).data, status=status.HTTP_201_CREATED)


class CostCenterDetailView(APIView):
    def patch(self, request, object_id):
        context = _context(request)
        _require_manage(context)
        obj = _get_scoped(CostCenter, context, object_id)
        serializer = CostCenterSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        audit_planning_change(
            membership=context.membership,
            legal_entity=context.legal_entity,
            action="planning.cost_center_updated",
            object_type="CostCenter",
            object_id=obj.id,
            state=CostCenterSerializer(obj).data,
            request=request,
        )
        return Response(CostCenterSerializer(obj).data)


class ProductListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = Product.objects.filter(legal_entity=context.legal_entity)
        return Response(ProductSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        _require_manage(context)
        serializer = ProductSerializer(data=request.data)
        obj = _save_master(
            request,
            context,
            serializer,
            object_type="Product",
            action="planning.product_created",
        )
        return Response(ProductSerializer(obj).data, status=status.HTTP_201_CREATED)


class ProductDetailView(APIView):
    def patch(self, request, object_id):
        context = _context(request)
        _require_manage(context)
        obj = _get_scoped(Product, context, object_id)
        serializer = ProductSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        audit_planning_change(
            membership=context.membership,
            legal_entity=context.legal_entity,
            action="planning.product_updated",
            object_type="Product",
            object_id=obj.id,
            state=ProductSerializer(obj).data,
            request=request,
        )
        return Response(ProductSerializer(obj).data)


class ProjectListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = Project.objects.filter(legal_entity=context.legal_entity).select_related("product")
        return Response(ProjectSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        _require_manage(context)
        serializer = ProjectSerializer(data=request.data)
        obj = _save_master(
            request,
            context,
            serializer,
            object_type="Project",
            action="planning.project_created",
        )
        return Response(ProjectSerializer(obj).data, status=status.HTTP_201_CREATED)


class ProjectDetailView(APIView):
    def patch(self, request, object_id):
        context = _context(request)
        _require_manage(context)
        obj = _get_scoped(Project, context, object_id)
        serializer = ProjectSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        audit_planning_change(
            membership=context.membership,
            legal_entity=context.legal_entity,
            action="planning.project_updated",
            object_type="Project",
            object_id=obj.id,
            state=ProjectSerializer(obj).data,
            request=request,
        )
        return Response(ProjectSerializer(obj).data)


class ExpenseAllocationView(APIView):
    def get(self, request, expense_id):
        context = _context(request)
        _require_view(context)
        expense = Expense.objects.filter(id=expense_id, legal_entity=context.legal_entity).first()
        if expense is None:
            raise ValidationError("Expense does not exist in the active legal entity.")
        return Response(ExpenseAllocationSerializer(expense.allocations.all(), many=True).data)

    def put(self, request, expense_id):
        context = _context(request)
        expense = Expense.objects.filter(id=expense_id, legal_entity=context.legal_entity).first()
        if expense is None:
            raise ValidationError("Expense does not exist in the active legal entity.")
        serializer = AllocationReplaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        allocations = replace_expense_allocations(
            membership=context.membership,
            expense=expense,
            allocations=serializer.validated_data["allocations"],
            request=request,
        )
        return Response(ExpenseAllocationSerializer(allocations, many=True).data)


class BudgetListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = Budget.objects.filter(legal_entity=context.legal_entity).prefetch_related("lines")
        return Response(BudgetSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        _require_manage(context)
        serializer = BudgetSerializer(data=request.data)
        obj = _save_master(
            request,
            context,
            serializer,
            object_type="Budget",
            action="planning.budget_created",
        )
        return Response(BudgetSerializer(obj).data, status=status.HTTP_201_CREATED)


class BudgetDetailView(APIView):
    def get(self, request, budget_id):
        context = _context(request)
        _require_view(context)
        budget = _get_scoped(Budget, context, budget_id)
        data = BudgetSerializer(budget).data
        data["lines"] = BudgetLineSerializer(budget.lines.all(), many=True).data
        return Response(data)

    def patch(self, request, budget_id):
        context = _context(request)
        _require_manage(context)
        budget = _get_scoped(Budget, context, budget_id)
        serializer = BudgetSerializer(budget, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        budget = serializer.save()
        audit_planning_change(
            membership=context.membership,
            legal_entity=context.legal_entity,
            action="planning.budget_updated",
            object_type="Budget",
            object_id=budget.id,
            state=BudgetSerializer(budget).data,
            request=request,
        )
        return Response(BudgetSerializer(budget).data)


class BudgetLineListCreateView(APIView):
    def get(self, request, budget_id):
        context = _context(request)
        _require_view(context)
        budget = _get_scoped(Budget, context, budget_id)
        return Response(BudgetLineSerializer(budget.lines.all(), many=True).data)

    def post(self, request, budget_id):
        context = _context(request)
        _require_manage(context)
        budget = _get_scoped(Budget, context, budget_id)
        serializer = BudgetLineCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        line = serializer.save(budget=budget)
        audit_planning_change(
            membership=context.membership,
            legal_entity=context.legal_entity,
            action="planning.budget_line_created",
            object_type="BudgetLine",
            object_id=line.id,
            state=BudgetLineSerializer(line).data,
            request=request,
        )
        return Response(BudgetLineSerializer(line).data, status=status.HTTP_201_CREATED)


class BudgetActualView(APIView):
    def get(self, request, budget_id):
        context = _context(request)
        _require_view(context)
        budget = _get_scoped(Budget, context, budget_id)
        return Response(budget_actuals(budget))
