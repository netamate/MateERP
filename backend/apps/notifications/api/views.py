from email.utils import parseaddr

from apps.audit.services import record_audit_event
from apps.identity.models import Membership, MembershipStatus
from apps.identity.policy import Permission, has_permission
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from ..crypto import encrypt_secret
from ..models import (
    Notification,
    NotificationDelivery,
    NotificationIntegrationSettings,
)
from ..services import (
    integration_settings_payload,
    mark_all_notifications_read,
    mark_notification_read,
    send_test_email,
    send_test_hermes,
)
from .serializers import (
    NotificationDeliverySerializer,
    NotificationIntegrationSettingsSerializer,
    NotificationSerializer,
    TestEmailSerializer,
    TestHermesSerializer,
)


def _membership(request, permission=Permission.VIEW_NOTIFICATIONS):
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


def _integration_instance(organization):
    existing = NotificationIntegrationSettings.objects.filter(organization=organization).first()
    if existing:
        return existing

    _, from_email = parseaddr(settings.DEFAULT_FROM_EMAIL)
    return NotificationIntegrationSettings(
        organization=organization,
        smtp_enabled=bool(settings.EMAIL_HOST),
        smtp_host=settings.EMAIL_HOST,
        smtp_port=settings.EMAIL_PORT,
        smtp_username=settings.EMAIL_HOST_USER,
        smtp_password_encrypted=encrypt_secret(settings.EMAIL_HOST_PASSWORD),
        smtp_use_tls=settings.EMAIL_USE_TLS,
        smtp_use_ssl=settings.EMAIL_USE_SSL,
        smtp_from_name="MateERP",
        smtp_from_email=from_email,
        hermes_enabled=bool(settings.MATEERP_HERMES_WEBHOOK_URL),
        hermes_webhook_url=settings.MATEERP_HERMES_WEBHOOK_URL,
        hermes_token_encrypted=encrypt_secret(settings.MATEERP_HERMES_WEBHOOK_TOKEN),
    )


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


class NotificationIntegrationSettingsView(APIView):
    def get(self, request):
        membership = _membership(request, Permission.VIEW_ORGANIZATION)
        return Response(integration_settings_payload(membership.organization))

    def patch(self, request):
        membership = _membership(request, Permission.MANAGE_ORGANIZATION)
        previous = integration_settings_payload(membership.organization)
        integration = _integration_instance(membership.organization)
        serializer = NotificationIntegrationSettingsSerializer(
            integration,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        validated = dict(serializer.validated_data)

        smtp_password = validated.pop("smtp_password", None)
        hermes_token = validated.pop("hermes_token", None)
        for field, value in validated.items():
            setattr(integration, field, value)
        if smtp_password is not None:
            integration.smtp_password_encrypted = encrypt_secret(smtp_password)
        if hermes_token is not None:
            integration.hermes_token_encrypted = encrypt_secret(hermes_token)

        if integration.smtp_enabled:
            if not integration.smtp_host or not integration.smtp_from_email:
                raise ValidationError("SMTP Host and From Email are required when SMTP is enabled.")
            if integration.smtp_username and not integration.smtp_password_encrypted:
                raise ValidationError(
                    "SMTP Password is required when an SMTP Username is configured."
                )
        if integration.hermes_enabled and not integration.hermes_webhook_url:
            raise ValidationError("Hermes Webhook URL is required when Hermes is enabled.")

        integration.updated_by = request.user
        integration.save()
        current = integration_settings_payload(membership.organization)
        record_audit_event(
            actor=request.user,
            organization=membership.organization,
            action="settings.notification_integrations_updated",
            object_type="NotificationIntegrationSettings",
            object_id=integration.id,
            previous_state=previous,
            new_state=current,
            request=request,
        )
        return Response(current)


class NotificationIntegrationEmailTestView(APIView):
    def post(self, request):
        membership = _membership(request, Permission.MANAGE_ORGANIZATION)
        serializer = TestEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        destination = serializer.validated_data["recipient"]
        try:
            send_test_email(
                organization=membership.organization,
                destination=destination,
            )
        except Exception as exc:
            raise ValidationError(f"SMTP test failed: {exc}") from exc

        record_audit_event(
            actor=request.user,
            organization=membership.organization,
            action="settings.smtp_test_sent",
            object_type="NotificationIntegrationSettings",
            object_id=membership.organization_id,
            new_state={"recipient": destination, "result": "success"},
            request=request,
        )
        return Response({"detail": f"Test email sent to {destination}."})


class NotificationIntegrationHermesTestView(APIView):
    def post(self, request):
        membership = _membership(request, Permission.MANAGE_ORGANIZATION)
        serializer = TestHermesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = serializer.validated_data.get("target", "")
        try:
            send_test_hermes(
                organization=membership.organization,
                target=target,
            )
        except Exception as exc:
            raise ValidationError(f"Hermes test failed: {exc}") from exc

        record_audit_event(
            actor=request.user,
            organization=membership.organization,
            action="settings.hermes_test_sent",
            object_type="NotificationIntegrationSettings",
            object_id=membership.organization_id,
            new_state={"target": target or "default", "result": "success"},
            request=request,
        )
        return Response({"detail": "Hermes test notification sent."})
