from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.policy import Permission, has_permission
from apps.identity.services import set_active_context

from ..models import (
    ApprovalAction,
    Expense,
    FinanceDocument,
    FinancialAccount,
    FounderFunding,
    Income,
    Reimbursement,
    Transfer,
    Vendor,
)
from ..selectors import financial_account_transactions
from ..services import (
    approve_expense,
    approve_reimbursement,
    create_expense,
    create_reimbursement,
    pay_expense,
    pay_reimbursement,
    record_founder_funding,
    record_income,
    record_transfer,
    reject_expense,
    reject_reimbursement,
    submit_expense,
    submit_reimbursement,
)
from .serializers import (
    ApprovalActionSerializer,
    ExpensePaymentSerializer,
    ExpenseSerializer,
    FinanceDocumentSerializer,
    FinancialAccountSerializer,
    FounderFundingSerializer,
    IncomeSerializer,
    PaymentCreateSerializer,
    ReimbursementPaymentSerializer,
    ReimbursementSerializer,
    TransferSerializer,
    VendorSerializer,
    WorkflowActionSerializer,
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
    if not has_permission(context.membership, Permission.VIEW_FINANCE):
        raise PermissionDenied("You do not have permission to view finance operations.")


def _get_scoped(model, context, object_id):
    obj = model.objects.filter(id=object_id, legal_entity=context.legal_entity).first()
    if obj is None:
        raise ValidationError("Finance record does not exist in the active legal entity.")
    return obj


class VendorListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = Vendor.objects.filter(legal_entity=context.legal_entity)
        return Response(VendorSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        if not has_permission(context.membership, Permission.MANAGE_FINANCE):
            raise PermissionDenied("You cannot manage vendors.")
        serializer = VendorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendor = serializer.save(legal_entity=context.legal_entity)
        return Response(VendorSerializer(vendor).data, status=status.HTTP_201_CREATED)


class FinancialAccountListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = FinancialAccount.objects.filter(legal_entity=context.legal_entity)
        return Response(FinancialAccountSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        if not has_permission(context.membership, Permission.MANAGE_FINANCE):
            raise PermissionDenied("You cannot manage financial accounts.")
        serializer = FinancialAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        financial_account = serializer.save(legal_entity=context.legal_entity)
        return Response(
            FinancialAccountSerializer(financial_account).data,
            status=status.HTTP_201_CREATED,
        )


class FinancialAccountTransactionView(APIView):
    def get(self, request, account_id):
        context = _context(request)
        _require_view(context)
        account = _get_scoped(FinancialAccount, context, account_id)
        return Response(financial_account_transactions(account))


class ExpenseListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = Expense.objects.filter(legal_entity=context.legal_entity).prefetch_related(
            "payments"
        )
        return Response(ExpenseSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        serializer = ExpenseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        expense = create_expense(
            membership=context.membership,
            legal_entity=context.legal_entity,
            request=request,
            **serializer.validated_data,
        )
        return Response(ExpenseSerializer(expense).data, status=status.HTTP_201_CREATED)


class ExpenseWorkflowView(APIView):
    def post(self, request, expense_id):
        context = _context(request)
        expense = _get_scoped(Expense, context, expense_id)
        serializer = WorkflowActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        comment = serializer.validated_data.get("comment", "")
        if action == "submit":
            expense = submit_expense(
                membership=context.membership,
                expense=expense,
                comment=comment,
                request=request,
            )
        elif action == "approve":
            expense = approve_expense(
                membership=context.membership,
                expense=expense,
                comment=comment,
                request=request,
            )
        else:
            expense = reject_expense(
                membership=context.membership,
                expense=expense,
                reason=comment,
                request=request,
            )
        return Response(ExpenseSerializer(expense).data)


class ExpensePaymentCreateView(APIView):
    def post(self, request, expense_id):
        context = _context(request)
        expense = _get_scoped(Expense, context, expense_id)
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = pay_expense(
            membership=context.membership,
            expense=expense,
            request=request,
            **serializer.validated_data,
        )
        return Response(
            ExpensePaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )


class IncomeListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = Income.objects.filter(legal_entity=context.legal_entity)
        return Response(IncomeSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        serializer = IncomeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        income = record_income(
            membership=context.membership,
            legal_entity=context.legal_entity,
            request=request,
            **serializer.validated_data,
        )
        return Response(IncomeSerializer(income).data, status=status.HTTP_201_CREATED)


class TransferListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = Transfer.objects.filter(legal_entity=context.legal_entity)
        return Response(TransferSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transfer = record_transfer(
            membership=context.membership,
            legal_entity=context.legal_entity,
            request=request,
            **serializer.validated_data,
        )
        return Response(TransferSerializer(transfer).data, status=status.HTTP_201_CREATED)


class FounderFundingListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = FounderFunding.objects.filter(legal_entity=context.legal_entity)
        return Response(FounderFundingSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        serializer = FounderFundingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        funding = record_founder_funding(
            membership=context.membership,
            legal_entity=context.legal_entity,
            request=request,
            **serializer.validated_data,
        )
        return Response(
            FounderFundingSerializer(funding).data,
            status=status.HTTP_201_CREATED,
        )


class ReimbursementListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = Reimbursement.objects.filter(legal_entity=context.legal_entity).prefetch_related(
            "payments"
        )
        return Response(ReimbursementSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        serializer = ReimbursementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reimbursement = create_reimbursement(
            membership=context.membership,
            legal_entity=context.legal_entity,
            request=request,
            **serializer.validated_data,
        )
        return Response(
            ReimbursementSerializer(reimbursement).data,
            status=status.HTTP_201_CREATED,
        )


class ReimbursementWorkflowView(APIView):
    def post(self, request, reimbursement_id):
        context = _context(request)
        reimbursement = _get_scoped(Reimbursement, context, reimbursement_id)
        serializer = WorkflowActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        comment = serializer.validated_data.get("comment", "")
        if action == "submit":
            reimbursement = submit_reimbursement(
                membership=context.membership,
                reimbursement=reimbursement,
                comment=comment,
                request=request,
            )
        elif action == "approve":
            reimbursement = approve_reimbursement(
                membership=context.membership,
                reimbursement=reimbursement,
                comment=comment,
                request=request,
            )
        else:
            reimbursement = reject_reimbursement(
                membership=context.membership,
                reimbursement=reimbursement,
                reason=comment,
                request=request,
            )
        return Response(ReimbursementSerializer(reimbursement).data)


class ReimbursementPaymentCreateView(APIView):
    def post(self, request, reimbursement_id):
        context = _context(request)
        reimbursement = _get_scoped(Reimbursement, context, reimbursement_id)
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = pay_reimbursement(
            membership=context.membership,
            reimbursement=reimbursement,
            request=request,
            **serializer.validated_data,
        )
        return Response(
            ReimbursementPaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )


class ApprovalActionListView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = ApprovalAction.objects.filter(legal_entity=context.legal_entity).select_related(
            "actor"
        )
        return Response(ApprovalActionSerializer(queryset, many=True).data)


class FinanceDocumentListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = FinanceDocument.objects.filter(legal_entity=context.legal_entity)
        return Response(FinanceDocumentSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        if not has_permission(context.membership, Permission.MANAGE_FINANCE_DOCUMENTS):
            raise PermissionDenied("You cannot upload finance documents.")
        serializer = FinanceDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data.get("file")
        document = serializer.save(
            legal_entity=context.legal_entity,
            uploaded_by=request.user,
            original_name=getattr(upload, "name", "finance-document"),
        )
        return Response(
            FinanceDocumentSerializer(document).data,
            status=status.HTTP_201_CREATED,
        )
