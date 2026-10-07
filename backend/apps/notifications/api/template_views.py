from smtplib import SMTPAuthenticationError, SMTPException

from apps.audit.services import record_audit_event
from apps.identity.models import Membership, MembershipStatus
from apps.identity.policy import Permission, has_permission
from apps.identity.selectors import accessible_legal_entities
from django.db import IntegrityError
from django.db.models import Q
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from ..email_templates import (
    create_email_template,
    ensure_default_email_templates,
    render_email_content,
    sample_context,
    update_email_template,
)
from ..models import EmailTemplate, EmailTemplateStatus
from ..services import _send_email
from .template_serializers import (
    EmailTemplatePreviewSerializer,
    EmailTemplateSerializer,
    EmailTemplateTestSerializer,
    EmailTemplateVersionSerializer,
)


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
    entity_id = request.session.get("active_legal_entity_id")
    if not entity_id:
        return None
    entity = accessible_legal_entities(membership).filter(id=entity_id).first()
    if entity is None:
        raise ValidationError("The active legal entity is not accessible.")
    return entity


def _template(membership, template_id):
    template = (
        EmailTemplate.objects.filter(
            id=template_id,
            organization=membership.organization,
        )
        .select_related("legal_entity", "created_by", "updated_by")
        .first()
    )
    if template is None:
        raise ValidationError("Email template does not exist in this organization.")
    if (
        template.legal_entity_id
        and not accessible_legal_entities(membership).filter(id=template.legal_entity_id).exists()
    ):
        raise PermissionDenied("You cannot access this legal entity template.")
    return template


class EmailTemplateListCreateView(APIView):
    def get(self, request):
        membership = _membership(request, Permission.VIEW_NOTIFICATIONS)
        ensure_default_email_templates(membership.organization, actor=request.user)
        queryset = (
            EmailTemplate.objects.filter(organization=membership.organization)
            .select_related("legal_entity", "created_by", "updated_by")
            .prefetch_related("versions")
        )
        entity = _active_entity(request, membership)
        if entity:
            queryset = queryset.filter(Q(legal_entity__isnull=True) | Q(legal_entity=entity))
        if request.query_params.get("include_archived") not in {"1", "true", "yes"}:
            queryset = queryset.filter(status=EmailTemplateStatus.ACTIVE)
        signal = request.query_params.get("signal")
        if signal:
            queryset = queryset.filter(signal=signal)
        return Response(EmailTemplateSerializer(queryset.distinct(), many=True).data)

    def post(self, request):
        membership = _membership(request, Permission.MANAGE_NOTIFICATIONS)
        serializer = EmailTemplateSerializer(
            data=request.data,
            context={"organization": membership.organization},
        )
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        try:
            template = create_email_template(
                organization=membership.organization,
                actor=request.user,
                data=data,
            )
        except IntegrityError as exc:
            raise ValidationError({"template_key": "This template key already exists."}) from exc
        record_audit_event(
            actor=request.user,
            organization=membership.organization,
            legal_entity=template.legal_entity,
            action="notifications.email_template_created",
            object_type="EmailTemplate",
            object_id=template.id,
            new_state={
                "name": template.name,
                "template_key": template.template_key,
                "signal": template.signal,
                "version": template.current_version,
            },
            request=request,
        )
        return Response(
            EmailTemplateSerializer(template).data,
            status=status.HTTP_201_CREATED,
        )


class EmailTemplateDetailView(APIView):
    def get(self, request, template_id):
        membership = _membership(request, Permission.VIEW_NOTIFICATIONS)
        return Response(EmailTemplateSerializer(_template(membership, template_id)).data)

    def patch(self, request, template_id):
        membership = _membership(request, Permission.MANAGE_NOTIFICATIONS)
        template = _template(membership, template_id)
        previous = EmailTemplateSerializer(template).data
        serializer = EmailTemplateSerializer(
            template,
            data=request.data,
            partial=True,
            context={"organization": membership.organization},
        )
        serializer.is_valid(raise_exception=True)
        try:
            template = update_email_template(
                template=template,
                actor=request.user,
                data=dict(serializer.validated_data),
            )
        except IntegrityError as exc:
            raise ValidationError({"template_key": "This template key already exists."}) from exc
        record_audit_event(
            actor=request.user,
            organization=membership.organization,
            legal_entity=template.legal_entity,
            action="notifications.email_template_updated",
            object_type="EmailTemplate",
            object_id=template.id,
            previous_state={
                "name": previous["name"],
                "signal": previous["signal"],
                "version": previous["current_version"],
                "status": previous["status"],
            },
            new_state={
                "name": template.name,
                "signal": template.signal,
                "version": template.current_version,
                "status": template.status,
            },
            request=request,
        )
        return Response(EmailTemplateSerializer(template).data)


class EmailTemplateArchiveView(APIView):
    def post(self, request, template_id):
        membership = _membership(request, Permission.MANAGE_NOTIFICATIONS)
        template = _template(membership, template_id)
        if template.alert_rules.filter(enabled=True).exists():
            raise ValidationError(
                "Disable or change active alert rules that use this template before archiving it."
            )
        template = update_email_template(
            template=template,
            actor=request.user,
            data={"status": EmailTemplateStatus.ARCHIVED},
        )
        record_audit_event(
            actor=request.user,
            organization=membership.organization,
            legal_entity=template.legal_entity,
            action="notifications.email_template_archived",
            object_type="EmailTemplate",
            object_id=template.id,
            new_state={"status": template.status, "version": template.current_version},
            request=request,
        )
        return Response(EmailTemplateSerializer(template).data)


class EmailTemplateVersionListView(APIView):
    def get(self, request, template_id):
        membership = _membership(request, Permission.VIEW_NOTIFICATIONS)
        template = _template(membership, template_id)
        return Response(EmailTemplateVersionSerializer(template.versions.all(), many=True).data)


class EmailTemplatePreviewView(APIView):
    def post(self, request):
        membership = _membership(request, Permission.VIEW_NOTIFICATIONS)
        serializer = EmailTemplatePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        entity = _active_entity(request, membership)
        context = sample_context(
            data.get("signal"),
            organization=membership.organization,
            legal_entity=entity,
        )
        context.update(data.get("context") or {})
        try:
            rendered = render_email_content(
                signal=data.get("signal"),
                subject_template=data["subject_template"],
                text_body_template=data["text_body_template"],
                html_body_template=data.get("html_body_template", ""),
                context=context,
            )
        except Exception as exc:
            raise ValidationError(str(exc)) from exc
        return Response({**rendered, "context": context})


class EmailTemplateTestView(APIView):
    def post(self, request):
        membership = _membership(request, Permission.MANAGE_NOTIFICATIONS)
        serializer = EmailTemplateTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        entity = _active_entity(request, membership)
        context = sample_context(
            data.get("signal"),
            organization=membership.organization,
            legal_entity=entity,
        )
        context.update(data.get("context") or {})
        context["recipient_email"] = data["recipient"]
        rendered = render_email_content(
            signal=data.get("signal"),
            subject_template=data["subject_template"],
            text_body_template=data["text_body_template"],
            html_body_template=data.get("html_body_template", ""),
            context=context,
        )
        try:
            _send_email(
                organization=membership.organization,
                destination=data["recipient"],
                subject=rendered["subject"],
                message=rendered["text_body"],
                html_message=rendered["html_body"],
            )
        except SMTPAuthenticationError as exc:
            raise ValidationError(
                "SMTP authentication was rejected. Check the mailbox username and password."
            ) from exc
        except SMTPException as exc:
            raise ValidationError("SMTP server rejected the template test email.") from exc
        except (TimeoutError, OSError) as exc:
            raise ValidationError("Could not connect to the SMTP server.") from exc
        except RuntimeError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(
            {
                "detail": (
                    f"SMTP accepted the template test email for {data['recipient']}. "
                    "This preview draft was not saved."
                ),
                "subject": rendered["subject"],
            }
        )