from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.models import Membership, MembershipStatus
from apps.identity.policy import Permission, has_permission

from ..models import Notification, NotificationDelivery
from ..services import mark_all_notifications_read, mark_notification_read
from .serializers import NotificationDeliverySerializer, NotificationSerializer


def _membership(request):
    organization_id = request.session.get("active_organization_id")
    if not organization_id:
        raise ValidationError("Select an active organization first.")
    membership = Membership.objects.filter(
        user=request.user,
        organization_id=organization_id,
        status=MembershipStatus.ACTIVE,
    ).first()
    if not membership or not has_permission(membership, Permission.VIEW_NOTIFICATIONS):
        raise PermissionDenied("You do not have permission to view notifications.")
    return membership


def _inbox(request, membership):
    queryset = Notification.objects.filter(
        organization=membership.organization,
        recipient=request.user,
    )
    legal_entity_id = request.session.get("active_legal_entity_id")
    if legal_entity_id:
        queryset = queryset.filter(
            Q(legal_entity_id=legal_entity_id) | Q(legal_entity__isnull=True)
        )
    return queryset


class NotificationListView(APIView):
    def get(self, request):
        membership = _membership(request)
        all_notifications = _inbox(request, membership)
        unread_count = all_notifications.filter(
            read_at__isnull=True,
            resolved_at__isnull=True,
        ).count()
        queryset = all_notifications
        if request.query_params.get("include_resolved") not in {"1", "true", "yes"}:
            queryset = queryset.filter(resolved_at__isnull=True)
        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(queryset, request)
        response = paginator.get_paginated_response(NotificationSerializer(page, many=True).data)
        response.data["unread_count"] = unread_count
        return response


class NotificationReadView(APIView):
    def post(self, request, notification_id):
        membership = _membership(request)
        notification = _inbox(request, membership).filter(id=notification_id).first()
        if notification is None:
            raise ValidationError("Notification does not exist in the active context.")
        notification = mark_notification_read(notification)
        return Response(NotificationSerializer(notification).data)


class NotificationReadAllView(APIView):
    def post(self, request):
        membership = _membership(request)
        count = mark_all_notifications_read(
            _inbox(request, membership).filter(resolved_at__isnull=True)
        )
        return Response({"marked_read": count})


class NotificationDeliveryListView(APIView):
    def get(self, request):
        membership = _membership(request)
        legal_entity_id = request.session.get("active_legal_entity_id")
        queryset = NotificationDelivery.objects.filter(
            organization=membership.organization
        ).select_related("subscription")
        if legal_entity_id:
            queryset = queryset.filter(legal_entity_id=legal_entity_id)

        paginator = PageNumberPagination()
        paginator.page_size = 100
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(
            NotificationDeliverySerializer(page, many=True).data
        )
