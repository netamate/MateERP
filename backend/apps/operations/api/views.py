from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.policy import Permission, has_permission
from apps.identity.services import set_active_context

from ..models import Domain, InfrastructureAsset, Subscription
from ..selectors import renewal_calendar
from ..services import audit_operations_change, renew_domain
from .serializers import (
    DomainRenewActionSerializer,
    DomainRenewalSerializer,
    DomainSerializer,
    InfrastructureAssetSerializer,
    RenewalQuerySerializer,
    SubscriptionSerializer,
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
    if not has_permission(context.membership, Permission.VIEW_OPERATIONS):
        raise PermissionDenied("You do not have permission to view operations data.")


def _require_manage(context):
    if not has_permission(context.membership, Permission.MANAGE_OPERATIONS):
        raise PermissionDenied("You do not have permission to manage operations data.")


def _get_scoped(model, context, object_id):
    obj = model.objects.filter(id=object_id, legal_entity=context.legal_entity).first()
    if obj is None:
        raise ValidationError("Operations record does not exist in the active legal entity.")
    return obj


def _create_master(request, context, serializer, *, object_type: str, action: str):
    serializer.is_valid(raise_exception=True)
    obj = serializer.save(legal_entity=context.legal_entity)
    audit_operations_change(
        membership=context.membership,
        legal_entity=context.legal_entity,
        action=action,
        object_type=object_type,
        object_id=obj.id,
        state=serializer.__class__(obj).data,
        request=request,
    )
    return obj


def _update_master(request, context, obj, serializer, *, object_type: str, action: str):
    serializer.is_valid(raise_exception=True)
    obj = serializer.save()
    audit_operations_change(
        membership=context.membership,
        legal_entity=context.legal_entity,
        action=action,
        object_type=object_type,
        object_id=obj.id,
        state=serializer.__class__(obj).data,
        request=request,
    )
    return obj


class SubscriptionListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = Subscription.objects.filter(
            legal_entity=context.legal_entity
        ).select_related("vendor")
        return Response(SubscriptionSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        _require_manage(context)
        serializer = SubscriptionSerializer(data=request.data)
        obj = _create_master(
            request,
            context,
            serializer,
            object_type="Subscription",
            action="operations.subscription_created",
        )
        return Response(SubscriptionSerializer(obj).data, status=status.HTTP_201_CREATED)


class SubscriptionDetailView(APIView):
    def get(self, request, object_id):
        context = _context(request)
        _require_view(context)
        return Response(
            SubscriptionSerializer(_get_scoped(Subscription, context, object_id)).data
        )

    def patch(self, request, object_id):
        context = _context(request)
        _require_manage(context)
        obj = _get_scoped(Subscription, context, object_id)
        serializer = SubscriptionSerializer(obj, data=request.data, partial=True)
        obj = _update_master(
            request,
            context,
            obj,
            serializer,
            object_type="Subscription",
            action="operations.subscription_updated",
        )
        return Response(SubscriptionSerializer(obj).data)


class DomainListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = Domain.objects.filter(legal_entity=context.legal_entity).select_related(
            "product"
        )
        return Response(DomainSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        _require_manage(context)
        serializer = DomainSerializer(data=request.data)
        obj = _create_master(
            request,
            context,
            serializer,
            object_type="Domain",
            action="operations.domain_created",
        )
        return Response(DomainSerializer(obj).data, status=status.HTTP_201_CREATED)


class DomainDetailView(APIView):
    def get(self, request, object_id):
        context = _context(request)
        _require_view(context)
        return Response(DomainSerializer(_get_scoped(Domain, context, object_id)).data)

    def patch(self, request, object_id):
        context = _context(request)
        _require_manage(context)
        obj = _get_scoped(Domain, context, object_id)
        serializer = DomainSerializer(obj, data=request.data, partial=True)
        obj = _update_master(
            request,
            context,
            obj,
            serializer,
            object_type="Domain",
            action="operations.domain_updated",
        )
        return Response(DomainSerializer(obj).data)


class DomainRenewalHistoryView(APIView):
    def get(self, request, domain_id):
        context = _context(request)
        _require_view(context)
        domain = _get_scoped(Domain, context, domain_id)
        return Response(DomainRenewalSerializer(domain.renewal_history.all(), many=True).data)


class DomainRenewView(APIView):
    def post(self, request, domain_id):
        context = _context(request)
        domain = _get_scoped(Domain, context, domain_id)
        serializer = DomainRenewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        renewal = renew_domain(
            membership=context.membership,
            domain=domain,
            request=request,
            **serializer.validated_data,
        )
        return Response(DomainRenewalSerializer(renewal).data, status=status.HTTP_201_CREATED)


class InfrastructureAssetListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = InfrastructureAsset.objects.filter(
            legal_entity=context.legal_entity
        ).select_related("vendor", "product", "cost_center")
        return Response(InfrastructureAssetSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        _require_manage(context)
        serializer = InfrastructureAssetSerializer(data=request.data)
        obj = _create_master(
            request,
            context,
            serializer,
            object_type="InfrastructureAsset",
            action="operations.infrastructure_created",
        )
        return Response(InfrastructureAssetSerializer(obj).data, status=status.HTTP_201_CREATED)


class InfrastructureAssetDetailView(APIView):
    def get(self, request, object_id):
        context = _context(request)
        _require_view(context)
        return Response(
            InfrastructureAssetSerializer(_get_scoped(InfrastructureAsset, context, object_id)).data
        )

    def patch(self, request, object_id):
        context = _context(request)
        _require_manage(context)
        obj = _get_scoped(InfrastructureAsset, context, object_id)
        serializer = InfrastructureAssetSerializer(obj, data=request.data, partial=True)
        obj = _update_master(
            request,
            context,
            obj,
            serializer,
            object_type="InfrastructureAsset",
            action="operations.infrastructure_updated",
        )
        return Response(InfrastructureAssetSerializer(obj).data)


class RenewalCalendarView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        serializer = RenewalQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return Response(
            renewal_calendar(
                context.legal_entity,
                start_date=serializer.validated_data.get("start_date"),
                end_date=serializer.validated_data.get("end_date"),
            )
        )
