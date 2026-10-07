from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.policy import Permission, has_permission
from apps.identity.services import set_active_context

from ..models import Subscription
from ..selectors import renewal_calendar
from ..services import audit_operations_change, record_subscription_payment
from .serializers import (
    RenewalQuerySerializer,
    SubscriptionPaymentActionSerializer,
    SubscriptionPaymentSerializer,
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


def _get_subscription(context, object_id):
    subscription = (
        Subscription.objects.filter(
            id=object_id,
            legal_entity=context.legal_entity,
        )
        .select_related("vendor")
        .prefetch_related("payments")
        .first()
    )
    if subscription is None:
        raise ValidationError("Subscription does not exist in the active legal entity.")
    return subscription


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
        queryset = (
            Subscription.objects.filter(legal_entity=context.legal_entity)
            .select_related("vendor")
            .prefetch_related("payments")
        )
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
        return Response(SubscriptionSerializer(_get_subscription(context, object_id)).data)

    def patch(self, request, object_id):
        context = _context(request)
        _require_manage(context)
        obj = _get_subscription(context, object_id)
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


class SubscriptionPaymentHistoryView(APIView):
    def get(self, request, object_id):
        context = _context(request)
        _require_view(context)
        subscription = _get_subscription(context, object_id)
        return Response(SubscriptionPaymentSerializer(subscription.payments.all(), many=True).data)


class SubscriptionMarkPaidView(APIView):
    def post(self, request, object_id):
        context = _context(request)
        _require_manage(context)
        subscription = _get_subscription(context, object_id)
        serializer = SubscriptionPaymentActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = record_subscription_payment(
            membership=context.membership,
            subscription=subscription,
            request=request,
            **serializer.validated_data,
        )
        return Response(
            SubscriptionPaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )


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
