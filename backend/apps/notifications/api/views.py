from email.utils import parseaddr
from smtplib import SMTPAuthenticationError, SMTPException

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.db.models import Q
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit_event
from apps.identity.models import Membership, MembershipStatus
from apps.identity.policy import Permission, has_permission

from ..crypto import encrypt_secret
from ..models import (
    AlertRule,
    Notification,
    NotificationDelivery,
    NotificationIntegrationSettings,
)
from ..services import (
    dismiss_notification,
    ensure_default_alert_rules,
    integration_settings_payload,
    mark_all_notifications_read,
    mark_notification_read,
    retry_notification_delivery,
    run_alert_rules,
    send_test_email,
    send_test_hermes,
)
from .serializers import (
    AlertRuleSerializer,
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
        kind = request.query_params.get("kind")
        severity = request.query_params.get("severity")
        state = request.query_params.get("state")
        if kind:
            queryset = queryset.filter(kind=kind)
        if severity:
            queryset = queryset.filter(severity=severity)
        if state == "UNREAD":
            queryset = queryset.filter(read_at__isnull=True, resolved_at__isnull=True)
        elif state == "READ":
            queryset = queryset.filter(read_at__isnull=False, resolved_at__isnull=True)
        elif state == "RESOLVED":
            queryset = queryset.filter(resolved_at__isnull=False)
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
        ).select_related("subscription", "alert_rule", "email_template")
        if legal_entity_id:
            queryset = queryset.filter(legal_entity_id=legal_entity_id)
        signal = request.query_params.get("signal")
        channel = request.query_params.get("channel")
        delivery_status = request.query_params.get("status")
        alert_rule = request.query_params.get("alert_rule")
        if signal:
            queryset = queryset.filter(signal=signal)
        if channel:
            queryset = queryset.filter(channel=channel)
        if delivery_status:
            queryset = queryset.filter(status=delivery_status)
        if alert_rule:
            queryset = queryset.filter(alert_rule_id=alert_rule)

        paginator = PageNumberPagination()
        paginator.page_size = 100
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(
            NotificationDeliverySerializer(page, many=True).data
        )


class NotificationDismissView(APIView):
    def post(self, request, notification_id):
        membership = _membership(request)
        notification = _inbox(request, membership).filter(id=notification_id).first()
        if notification is None:
            raise ValidationError("Notification does not exist in the active context.")
        notification = dismiss_notification(notification)
        return Response(NotificationSerializer(notification).data)


class AlertRuleListCreateView(APIView):
    def get(self, request):
        membership = _membership(request)
        ensure_default_alert_rules(membership.organization, actor=request.user)
        legal_entity_id = request.session.get("active_legal_entity_id")
        queryset = AlertRule.objects.filter(organization=membership.organization)
        if legal_entity_id:
            queryset = queryset.filter(
                Q(legal_entity__isnull=True) | Q(legal_entity_id=legal_entity_id)
            )
        return Response(AlertRuleSerializer(queryset, many=True).data)

    def post(self, request):
        membership = _membership(request, Permission.MANAGE_NOTIFICATIONS)
        serializer = AlertRuleSerializer(
            data=request.data,
            context={"organization": membership.organization},
        )
        serializer.is_valid(raise_exception=True)
        try:
            rule = serializer.save(
                organization=membership.organization,
                created_by=request.user,
                updated_by=request.user,
            )
        except IntegrityError as exc:
            raise ValidationError(
                "A rule for this signal already exists in the selected scope."
            ) from exc
        record_audit_event(
            actor=request.user,
            organization=membership.organization,
            legal_entity=rule.legal_entity,
            action="notifications.alert_rule_created",
            object_type="AlertRule",
            object_id=rule.id,
            new_state=AlertRuleSerializer(rule).data,
            request=request,
        )
        return Response(AlertRuleSerializer(rule).data, status=201)


class AlertRuleDetailView(APIView):
    def _rule(self, membership, rule_id):
        rule = AlertRule.objects.filter(
            id=rule_id,
            organization=membership.organization,
        ).first()
        if rule is None:
            raise ValidationError("Alert rule does not exist in this organization.")
        return rule

    def patch(self, request, rule_id):
        membership = _membership(request, Permission.MANAGE_NOTIFICATIONS)
        rule = self._rule(membership, rule_id)
        previous = AlertRuleSerializer(rule).data
        serializer = AlertRuleSerializer(
            rule,
            data=request.data,
            partial=True,
            context={"organization": membership.organization},
        )
        serializer.is_valid(raise_exception=True)
        try:
            rule = serializer.save(updated_by=request.user)
        except IntegrityError as exc:
            raise ValidationError(
                "A rule for this signal already exists in the selected scope."
            ) from exc
        current = AlertRuleSerializer(rule).data
        record_audit_event(
            actor=request.user,
            organization=membership.organization,
            legal_entity=rule.legal_entity,
            action="notifications.alert_rule_updated",
            object_type="AlertRule",
            object_id=rule.id,
            previous_state=previous,
            new_state=current,
            request=request,
        )
        return Response(current)


class AlertRuleRunNowView(APIView):
    def post(self, request):
        membership = _membership(request, Permission.MANAGE_NOTIFICATIONS)
        legal_entity = None
        legal_entity_id = request.session.get("active_legal_entity_id")
        if legal_entity_id:
            legal_entity = membership.organization.legal_entities.filter(id=legal_entity_id).first()
        result = run_alert_rules(
            organization=membership.organization,
            legal_entity=legal_entity,
            force=True,
        )
        record_audit_event(
            actor=request.user,
            organization=membership.organization,
            legal_entity=legal_entity,
            action="notifications.alert_rules_run_now",
            object_type="Organization",
            object_id=membership.organization_id,
            new_state={
                "rules_evaluated": result["rules_evaluated"],
                "active_events": result["active_events"],
                "deliveries_sent": result["deliveries_sent"],
                "deliveries_failed": result["deliveries_failed"],
            },
            request=request,
        )
        return Response(result)


class NotificationDeliveryRetryView(APIView):
    def post(self, request, delivery_id):
        membership = _membership(request, Permission.MANAGE_NOTIFICATIONS)
        delivery = (
            NotificationDelivery.objects.filter(
                id=delivery_id,
                organization=membership.organization,
            )
            .select_related("organization", "legal_entity", "subscription", "alert_rule")
            .first()
        )
        if delivery is None:
            raise ValidationError("Delivery does not exist in this organization.")
        legal_entity_id = request.session.get("active_legal_entity_id")
        if legal_entity_id and str(delivery.legal_entity_id) != str(legal_entity_id):
            raise ValidationError("Delivery does not exist in the active legal entity.")
        delivery = retry_notification_delivery(delivery)
        record_audit_event(
            actor=request.user,
            organization=membership.organization,
            legal_entity=delivery.legal_entity,
            action="notifications.delivery_retried",
            object_type="NotificationDelivery",
            object_id=delivery.id,
            new_state={
                "status": delivery.status,
                "attempt_count": delivery.attempt_count,
                "channel": delivery.channel,
                "signal": delivery.signal,
            },
            request=request,
        )
        return Response(NotificationDeliverySerializer(delivery).data)


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
        proposed = {
            key: value for key, value in serializer.validated_data.items() if key != "recipient"
        }
        try:
            send_test_email(
                organization=membership.organization,
                destination=destination,
                proposed=proposed,
            )
        except SMTPAuthenticationError as exc:
            raise ValidationError(
                "SMTP authentication was rejected. Check the mailbox username and password."
            ) from exc
        except SMTPException as exc:
            raise ValidationError(
                "SMTP server rejected the test. Check the sender, recipient and TLS settings."
            ) from exc
        except (TimeoutError, OSError) as exc:
            raise ValidationError(
                "Could not connect to the SMTP server. Check the host, port and TLS mode."
            ) from exc
        except RuntimeError as exc:
            raise ValidationError(str(exc)) from exc

        record_audit_event(
            actor=request.user,
            organization=membership.organization,
            action="settings.smtp_test_sent",
            object_type="NotificationIntegrationSettings",
            object_id=membership.organization_id,
            new_state={"recipient": destination, "result": "success"},
            request=request,
        )
        return Response(
            {
                "detail": (
                    f"SMTP accepted the test email for {destination}. "
                    "The draft settings have not been saved."
                )
            }
        )


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
