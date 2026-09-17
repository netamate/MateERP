from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.policy import Permission, has_permission
from apps.identity.services import set_active_context

from ..models import AccountReconciliation
from ..selectors import reconciliation_candidates
from ..services import (
    complete_reconciliation,
    create_reconciliation,
    replace_reconciliation_items,
)
from .serializers import (
    AccountReconciliationSerializer,
    ReconciliationCreateSerializer,
    ReconciliationItemsSerializer,
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


def _require(context, permission):
    if not has_permission(context.membership, permission):
        raise PermissionDenied("You do not have permission for account reconciliation.")


def _get_scoped(context, reconciliation_id):
    reconciliation = (
        AccountReconciliation.objects.filter(
            id=reconciliation_id,
            legal_entity=context.legal_entity,
        )
        .select_related("financial_account", "completed_by")
        .first()
    )
    if reconciliation is None:
        raise ValidationError("Reconciliation does not exist in the active legal entity.")
    return reconciliation


class ReconciliationListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require(context, Permission.VIEW_RECONCILIATION)
        queryset = AccountReconciliation.objects.filter(
            legal_entity=context.legal_entity
        ).select_related("financial_account", "completed_by")
        return Response(AccountReconciliationSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        _require(context, Permission.MANAGE_RECONCILIATION)
        serializer = ReconciliationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reconciliation = create_reconciliation(
            membership=context.membership,
            legal_entity=context.legal_entity,
            request=request,
            **serializer.validated_data,
        )
        return Response(
            AccountReconciliationSerializer(reconciliation).data,
            status=status.HTTP_201_CREATED,
        )


class ReconciliationDetailView(APIView):
    def get(self, request, reconciliation_id):
        context = _context(request)
        _require(context, Permission.VIEW_RECONCILIATION)
        reconciliation = _get_scoped(context, reconciliation_id)
        return Response(AccountReconciliationSerializer(reconciliation).data)


class ReconciliationCandidateView(APIView):
    def get(self, request, reconciliation_id):
        context = _context(request)
        _require(context, Permission.VIEW_RECONCILIATION)
        reconciliation = _get_scoped(context, reconciliation_id)
        return Response(reconciliation_candidates(reconciliation))


class ReconciliationItemsView(APIView):
    def put(self, request, reconciliation_id):
        context = _context(request)
        _require(context, Permission.MANAGE_RECONCILIATION)
        reconciliation = _get_scoped(context, reconciliation_id)
        serializer = ReconciliationItemsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reconciliation = replace_reconciliation_items(
            membership=context.membership,
            reconciliation=reconciliation,
            journal_line_ids=serializer.validated_data["journal_line_ids"],
            request=request,
        )
        return Response(AccountReconciliationSerializer(reconciliation).data)


class ReconciliationCompleteView(APIView):
    def post(self, request, reconciliation_id):
        context = _context(request)
        _require(context, Permission.MANAGE_RECONCILIATION)
        reconciliation = _get_scoped(context, reconciliation_id)
        reconciliation = complete_reconciliation(
            membership=context.membership,
            reconciliation=reconciliation,
            request=request,
        )
        return Response(AccountReconciliationSerializer(reconciliation).data)
