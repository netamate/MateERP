from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit_event
from apps.identity.models import Membership, MembershipStatus
from apps.identity.policy import Permission, has_permission
from apps.identity.selectors import accessible_legal_entities

from ..direct_email import deliver_direct_email
from ..models import DirectEmailNotification, DirectEmailStatus
from .email_serializers import DirectEmailNotificationSerializer


def _membership(request, permission):
    organization_id = request.session.get("active_organization_id")
    if not organization_id:
        raise ValidationError("Select an active organization first.")
    membership = Membership.objects.filter(
        user=request.user,
        organization_id=organization_id,
        status=MembershipStatus.ACTIVE,
    ).first()
    if not membership or not has_permission(membership, permission):
        raise PermissionDenied("You do not have permission for this action.")
    return membership


def _active_entity(request, membership):
    legal_entity_id = request.session.get("active_legal_entity_id")
    if not legal_entity_id:
        return None
    return accessible_legal_entities(membership).filter(id=legal_entity_id).first()


def _queryset(request, membership):
    queryset = DirectEmailNotification.objects.filter(
        organization=membership.organization
    ).select_related("created_by", "legal_entity")
    legal_entity_id = request.session.get("active_legal_entity_id")
    if legal_entity_id:
        queryset = queryset.filter(legal_entity_id=legal_entity_id)
    return queryset


class DirectEmailListCreateView(APIView):
    def get(self, request):
        membership = _membership(request, Permission.VIEW_NOTIFICATIONS)
        paginator = PageNumberPagination()
        paginator.page_size = 100
        page = paginator.paginate_queryset(_queryset(request, membership), request)
        return paginator.get_paginated_response(
            DirectEmailNotificationSerializer(page, many=True).data
        )

    def post(self, request):
        membership = _membership(request, Permission.MANAGE_ORGANIZATION)
        serializer = DirectEmailNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = dict(serializer.validated_data)
        action = validated.pop("action", "DRAFT")
        email_status = (
            DirectEmailStatus.SCHEDULED if action == "SCHEDULE" else DirectEmailStatus.DRAFT
        )
        if action == "SEND_NOW":
            validated["scheduled_for"] = None

        notification = DirectEmailNotification.objects.create(
            organization=membership.organization,
            legal_entity=_active_entity(request, membership),
            created_by=request.user,
            status=email_status,
            **validated,
        )
        if action == "SEND_NOW":
            notification = deliver_direct_email(notification.id)

        record_audit_event(
            actor=request.user,
            organization=membership.organization,
            legal_entity=notification.legal_entity,
            action="notifications.direct_email_created",
            object_type="DirectEmailNotification",
            object_id=notification.id,
            new_state={
                "status": notification.status,
                "to_recipients": notification.to_recipients,
                "subject": notification.subject,
                "scheduled_for": (
                    notification.scheduled_for.isoformat() if notification.scheduled_for else None
                ),
            },
            request=request,
        )
        return Response(
            DirectEmailNotificationSerializer(notification).data,
            status=status.HTTP_201_CREATED,
        )


class DirectEmailSendView(APIView):
    def post(self, request, notification_id):
        membership = _membership(request, Permission.MANAGE_ORGANIZATION)
        notification = _queryset(request, membership).filter(id=notification_id).first()
        if notification is None:
            raise ValidationError("Email notification does not exist in the active context.")
        if notification.status in {
            DirectEmailStatus.SENT,
            DirectEmailStatus.CANCELLED,
            DirectEmailStatus.SENDING,
        }:
            raise ValidationError(
                f"Cannot send an email notification in {notification.status} state."
            )
        notification = deliver_direct_email(notification.id)
        record_audit_event(
            actor=request.user,
            organization=membership.organization,
            legal_entity=notification.legal_entity,
            action="notifications.direct_email_send",
            object_type="DirectEmailNotification",
            object_id=notification.id,
            new_state={
                "status": notification.status,
                "attempt_count": notification.attempt_count,
            },
            request=request,
        )
        return Response(DirectEmailNotificationSerializer(notification).data)


class DirectEmailCancelView(APIView):
    def post(self, request, notification_id):
        membership = _membership(request, Permission.MANAGE_ORGANIZATION)
        notification = _queryset(request, membership).filter(id=notification_id).first()
        if notification is None:
            raise ValidationError("Email notification does not exist in the active context.")
        if notification.status in {DirectEmailStatus.SENT, DirectEmailStatus.SENDING}:
            raise ValidationError(
                f"Cannot cancel an email notification in {notification.status} state."
            )
        notification.status = DirectEmailStatus.CANCELLED
        notification.save(update_fields=["status", "updated_at"])
        record_audit_event(
            actor=request.user,
            organization=membership.organization,
            legal_entity=notification.legal_entity,
            action="notifications.direct_email_cancelled",
            object_type="DirectEmailNotification",
            object_id=notification.id,
            new_state={"status": notification.status},
            request=request,
        )
        return Response(DirectEmailNotificationSerializer(notification).data)
