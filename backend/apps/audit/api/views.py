from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView

from apps.identity.models import Membership, MembershipStatus
from apps.identity.policy import Permission, has_permission

from ..models import AuditEvent
from .serializers import AuditEventSerializer, AuditQuerySerializer


def _membership(request):
    organization_id = request.session.get("active_organization_id")
    if not organization_id:
        raise ValidationError("Select an active organization first.")
    membership = Membership.objects.filter(
        user=request.user,
        organization_id=organization_id,
        status=MembershipStatus.ACTIVE,
    ).first()
    if not membership or not has_permission(membership, Permission.VIEW_AUDIT_LOG):
        raise PermissionDenied("You do not have permission to view the audit log.")
    return membership


class AuditEventListView(APIView):
    def get(self, request):
        membership = _membership(request)
        serializer = AuditQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        queryset = AuditEvent.objects.filter(organization=membership.organization).select_related(
            "actor", "legal_entity"
        )
        legal_entity_id = request.session.get("active_legal_entity_id")
        if legal_entity_id:
            queryset = queryset.filter(
                Q(legal_entity_id=legal_entity_id) | Q(legal_entity__isnull=True)
            )
        if filters.get("action"):
            queryset = queryset.filter(action__icontains=filters["action"])
        if filters.get("object_type"):
            queryset = queryset.filter(object_type__icontains=filters["object_type"])
        if filters.get("actor_id"):
            queryset = queryset.filter(actor_id=filters["actor_id"])
        if filters.get("request_id"):
            queryset = queryset.filter(request_id=filters["request_id"])
        if filters.get("start_date"):
            queryset = queryset.filter(created_at__date__gte=filters["start_date"])
        if filters.get("end_date"):
            queryset = queryset.filter(created_at__date__lte=filters["end_date"])
        if filters.get("search"):
            search = filters["search"]
            queryset = queryset.filter(
                Q(action__icontains=search)
                | Q(object_type__icontains=search)
                | Q(object_id__icontains=search)
                | Q(actor__email__icontains=search)
                | Q(request_id__icontains=search)
            )

        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(AuditEventSerializer(page, many=True).data)
