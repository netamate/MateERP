from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit_event
from apps.finance.models import FinanceDocument
from apps.identity.policy import Permission, has_permission
from apps.identity.services import set_active_context

from ..services import create_finance_document_with_metadata
from .serializers import FinanceDocumentIntegritySerializer


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


class FinanceDocumentListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        if not has_permission(context.membership, Permission.VIEW_FINANCE):
            raise PermissionDenied("You cannot view finance documents.")
        queryset = (
            FinanceDocument.objects.filter(legal_entity=context.legal_entity)
            .select_related("uploaded_by", "integrity_metadata")
            .order_by("-created_at")
        )
        return Response(FinanceDocumentIntegritySerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        if not has_permission(context.membership, Permission.MANAGE_FINANCE_DOCUMENTS):
            raise PermissionDenied("You cannot upload finance documents.")
        serializer = FinanceDocumentIntegritySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = create_finance_document_with_metadata(
            legal_entity=context.legal_entity,
            uploaded_by=request.user,
            validated_data=serializer.validated_data,
        )
        record_audit_event(
            actor=request.user,
            organization=context.membership.organization,
            legal_entity=context.legal_entity,
            action="documents.finance_document_uploaded",
            object_type="FinanceDocument",
            object_id=document.id,
            new_state={
                "original_name": document.original_name,
                "document_type": document.document_type,
                "checksum_sha256": document.integrity_metadata.checksum_sha256,
            },
            request=request,
        )
        return Response(
            FinanceDocumentIntegritySerializer(document).data,
            status=status.HTTP_201_CREATED,
        )
