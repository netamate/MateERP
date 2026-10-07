from datetime import timedelta

from apps.audit.services import record_audit_event
from apps.identity.policy import Permission, has_permission
from apps.identity.services import set_active_context
from apps.notifications.crypto import decrypt_secret
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    AutomationPolicy,
    AutomationRun,
    RunStatus,
    RunTrigger,
    SyncStatus,
    VendorIntegration,
    VendorSyncRun,
)
from ..services import (
    VendorIntegrationError,
    ensure_default_automation_policies,
    run_automation_policy,
    sync_vendor_integration,
    test_vendor_configuration,
)
from .serializers import (
    AutomationOverviewSerializer,
    AutomationPolicySerializer,
    AutomationRunSerializer,
    VendorIntegrationSerializer,
    VendorIntegrationTestSerializer,
    VendorSyncRunSerializer,
)


def _context(request, permission):
    organization_id = request.session.get("active_organization_id")
    legal_entity_id = request.session.get("active_legal_entity_id")
    if not organization_id or not legal_entity_id:
        raise ValidationError("Select an active organization and legal entity first.")
    context = set_active_context(
        user=request.user,
        organization_id=organization_id,
        legal_entity_id=legal_entity_id,
    )
    if not has_permission(context.membership, permission):
        raise PermissionDenied("You do not have permission for automation management.")
    return context


def _integration(context, integration_id):
    integration = (
        VendorIntegration.objects.filter(
            id=integration_id,
            organization=context.organization,
            legal_entity=context.legal_entity,
        )
        .select_related("vendor", "subscription", "legal_entity", "organization")
        .first()
    )
    if integration is None:
        raise ValidationError("Vendor integration does not exist in the active legal entity.")
    return integration


def _policy(context, policy_id):
    policy = (
        AutomationPolicy.objects.filter(
            id=policy_id,
            organization=context.organization,
        )
        .filter(Q(legal_entity__isnull=True) | Q(legal_entity=context.legal_entity))
        .select_related("organization", "legal_entity")
        .first()
    )
    if policy is None:
        raise ValidationError("Automation policy does not exist in the active context.")
    return policy


class VendorIntegrationListCreateView(APIView):
    def get(self, request):
        context = _context(request, Permission.VIEW_AUTOMATION)
        queryset = (
            VendorIntegration.objects.filter(
                organization=context.organization,
                legal_entity=context.legal_entity,
            )
            .select_related("vendor", "subscription")
            .order_by("vendor__name", "name")
        )
        return Response(VendorIntegrationSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request, Permission.MANAGE_AUTOMATION)
        serializer = VendorIntegrationSerializer(
            data=request.data,
            context={
                "organization": context.organization,
                "legal_entity": context.legal_entity,
                "actor": request.user,
            },
        )
        serializer.is_valid(raise_exception=True)
        try:
            integration = serializer.save()
        except IntegrityError as exc:
            raise ValidationError(
                {"subscription": "This subscription already has a vendor integration."}
            ) from exc
        record_audit_event(
            actor=request.user,
            organization=context.organization,
            legal_entity=context.legal_entity,
            action="automation.vendor_integration_created",
            object_type="VendorIntegration",
            object_id=integration.id,
            new_state={
                "name": integration.name,
                "vendor_id": str(integration.vendor_id),
                "subscription_id": str(integration.subscription_id),
                "connector_type": integration.connector_type,
                "auth_type": integration.auth_type,
                "endpoint_host": integration.endpoint_url.split("/")[2],
                "secret_configured": bool(integration.secret_encrypted),
            },
            request=request,
        )
        return Response(
            VendorIntegrationSerializer(integration).data,
            status=status.HTTP_201_CREATED,
        )


class VendorIntegrationDetailView(APIView):
    def get(self, request, integration_id):
        context = _context(request, Permission.VIEW_AUTOMATION)
        return Response(VendorIntegrationSerializer(_integration(context, integration_id)).data)

    def patch(self, request, integration_id):
        context = _context(request, Permission.MANAGE_AUTOMATION)
        integration = _integration(context, integration_id)
        previous = VendorIntegrationSerializer(integration).data
        serializer = VendorIntegrationSerializer(
            integration,
            data=request.data,
            partial=True,
            context={
                "organization": context.organization,
                "legal_entity": context.legal_entity,
                "actor": request.user,
            },
        )
        serializer.is_valid(raise_exception=True)
        try:
            integration = serializer.save()
        except IntegrityError as exc:
            raise ValidationError(
                {"subscription": "This subscription already has a vendor integration."}
            ) from exc
        record_audit_event(
            actor=request.user,
            organization=context.organization,
            legal_entity=context.legal_entity,
            action="automation.vendor_integration_updated",
            object_type="VendorIntegration",
            object_id=integration.id,
            previous_state={
                "name": previous["name"],
                "enabled": previous["enabled"],
                "subscription": previous["subscription"],
                "auth_type": previous["auth_type"],
                "secret_configured": previous["secret_configured"],
            },
            new_state={
                "name": integration.name,
                "enabled": integration.enabled,
                "subscription_id": str(integration.subscription_id),
                "auth_type": integration.auth_type,
                "secret_configured": bool(integration.secret_encrypted),
            },
            request=request,
        )
        return Response(VendorIntegrationSerializer(integration).data)


class VendorIntegrationTestView(APIView):
    def post(self, request):
        context = _context(request, Permission.MANAGE_AUTOMATION)
        serializer = VendorIntegrationTestSerializer(
            data=request.data,
            context={"legal_entity": context.legal_entity},
        )
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        integration_id = data.pop("integration_id", None)
        subscription = data.pop("subscription")
        secret = data.get("secret") or ""
        integration = None
        if integration_id:
            integration = _integration(context, integration_id)
            if not secret and integration.secret_encrypted:
                secret = decrypt_secret(integration.secret_encrypted)
        data["secret"] = secret

        try:
            result = test_vendor_configuration(
                config=data,
                subscription=subscription,
            )
        except VendorIntegrationError as exc:
            if integration is not None:
                integration.last_test_at = timezone.now()
                integration.last_test_status = SyncStatus.FAILED
                integration.last_test_error = str(exc)[:2000]
                integration.save(
                    update_fields=[
                        "last_test_at",
                        "last_test_status",
                        "last_test_error",
                        "updated_at",
                    ]
                )
            raise ValidationError(str(exc)) from exc

        if integration is not None:
            integration.last_test_at = timezone.now()
            integration.last_test_status = SyncStatus.SUCCESS
            integration.last_test_error = ""
            integration.save(
                update_fields=[
                    "last_test_at",
                    "last_test_status",
                    "last_test_error",
                    "updated_at",
                ]
            )
        return Response(
            {
                "detail": "Vendor API test succeeded. Draft settings were not saved.",
                "http_status": result["http_status"],
                "cost_amount": str(result["cost_amount"]),
                "usage_quantity": (
                    str(result["usage_quantity"]) if result["usage_quantity"] is not None else None
                ),
                "currency": result["currency"],
                "usage_unit": result["usage_unit"],
            }
        )


class VendorIntegrationSyncView(APIView):
    def post(self, request, integration_id):
        context = _context(request, Permission.MANAGE_AUTOMATION)
        integration = _integration(context, integration_id)
        run = sync_vendor_integration(
            integration,
            trigger=RunTrigger.MANUAL,
            actor=request.user,
            request_obj=request,
        )
        payload = VendorSyncRunSerializer(run).data
        if run.status == RunStatus.FAILED:
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)


class VendorSyncRunListView(APIView):
    def get(self, request):
        context = _context(request, Permission.VIEW_AUTOMATION)
        queryset = (
            VendorSyncRun.objects.filter(
                integration__organization=context.organization,
                integration__legal_entity=context.legal_entity,
            )
            .select_related(
                "integration",
                "integration__vendor",
                "integration__subscription",
                "billing_period",
            )
            .order_by("-started_at")
        )
        integration_id = request.query_params.get("integration")
        run_status = request.query_params.get("status")
        if integration_id:
            queryset = queryset.filter(integration_id=integration_id)
        if run_status:
            queryset = queryset.filter(status=run_status)
        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(VendorSyncRunSerializer(page, many=True).data)


class AutomationPolicyListCreateView(APIView):
    def get(self, request):
        context = _context(request, Permission.VIEW_AUTOMATION)
        ensure_default_automation_policies(context.organization, actor=request.user)
        queryset = (
            AutomationPolicy.objects.filter(organization=context.organization)
            .filter(Q(legal_entity__isnull=True) | Q(legal_entity=context.legal_entity))
            .select_related("legal_entity")
        )
        return Response(AutomationPolicySerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request, Permission.MANAGE_AUTOMATION)
        serializer = AutomationPolicySerializer(
            data=request.data,
            context={"organization": context.organization},
        )
        serializer.is_valid(raise_exception=True)
        entity = serializer.validated_data.get("legal_entity")
        if entity is None:
            raise ValidationError({"legal_entity": "New policies must be legal-entity overrides."})
        if entity.id != context.legal_entity.id:
            raise ValidationError(
                {"legal_entity": "Choose the active legal entity for this override."}
            )
        try:
            policy = serializer.save(
                organization=context.organization,
                created_by=request.user,
                updated_by=request.user,
            )
        except IntegrityError as exc:
            raise ValidationError(
                "An automation policy for this kind already exists in the selected scope."
            ) from exc
        return Response(
            AutomationPolicySerializer(policy).data,
            status=status.HTTP_201_CREATED,
        )


class AutomationPolicyDetailView(APIView):
    def patch(self, request, policy_id):
        context = _context(request, Permission.MANAGE_AUTOMATION)
        policy = _policy(context, policy_id)
        serializer = AutomationPolicySerializer(
            policy,
            data=request.data,
            partial=True,
            context={"organization": context.organization},
        )
        serializer.is_valid(raise_exception=True)
        try:
            policy = serializer.save(updated_by=request.user)
        except IntegrityError as exc:
            raise ValidationError(
                "An automation policy for this kind already exists in the selected scope."
            ) from exc
        record_audit_event(
            actor=request.user,
            organization=context.organization,
            legal_entity=policy.legal_entity,
            action="automation.policy_updated",
            object_type="AutomationPolicy",
            object_id=policy.id,
            new_state={
                "kind": policy.kind,
                "enabled": policy.enabled,
                "frequency": policy.frequency,
                "schedule_hour": policy.schedule_hour,
                "schedule_timezone": policy.schedule_timezone,
            },
            request=request,
        )
        return Response(AutomationPolicySerializer(policy).data)


class AutomationPolicyRunView(APIView):
    def post(self, request, policy_id):
        context = _context(request, Permission.MANAGE_AUTOMATION)
        policy = _policy(context, policy_id)
        run = run_automation_policy(
            policy,
            trigger=RunTrigger.MANUAL,
            actor=request.user,
            request_obj=request,
        )
        payload = AutomationRunSerializer(run).data
        if run.status == RunStatus.FAILED:
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)


class AutomationRunListView(APIView):
    def get(self, request):
        context = _context(request, Permission.VIEW_AUTOMATION)
        queryset = (
            AutomationRun.objects.filter(policy__organization=context.organization)
            .filter(
                Q(policy__legal_entity__isnull=True) | Q(policy__legal_entity=context.legal_entity)
            )
            .select_related("policy")
            .order_by("-started_at")
        )
        run_status = request.query_params.get("status")
        kind = request.query_params.get("kind")
        if run_status:
            queryset = queryset.filter(status=run_status)
        if kind:
            queryset = queryset.filter(policy__kind=kind)
        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(AutomationRunSerializer(page, many=True).data)


class AutomationOverviewView(APIView):
    def get(self, request):
        context = _context(request, Permission.VIEW_AUTOMATION)
        since = timezone.now() - timedelta(hours=24)
        integrations = VendorIntegration.objects.filter(
            organization=context.organization,
            legal_entity=context.legal_entity,
        )
        policies = AutomationPolicy.objects.filter(
            organization=context.organization,
        ).filter(Q(legal_entity__isnull=True) | Q(legal_entity=context.legal_entity))
        runs = AutomationRun.objects.filter(
            policy__organization=context.organization,
            started_at__gte=since,
        ).filter(
            Q(policy__legal_entity__isnull=True) | Q(policy__legal_entity=context.legal_entity)
        )
        last_sync = (
            VendorSyncRun.objects.filter(
                integration__organization=context.organization,
                integration__legal_entity=context.legal_entity,
                status=RunStatus.SUCCESS,
            )
            .order_by("-finished_at")
            .values_list("finished_at", flat=True)
            .first()
        )
        payload = {
            "active_integrations": integrations.filter(enabled=True).count(),
            "failed_integrations": integrations.filter(last_sync_status=SyncStatus.FAILED).count(),
            "enabled_policies": policies.filter(enabled=True).count(),
            "failed_runs_24h": runs.filter(status=RunStatus.FAILED).count(),
            "last_vendor_sync_at": last_sync,
        }
        return Response(AutomationOverviewSerializer(payload).data)
