import mimetypes

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import FileResponse
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit_event
from apps.finance.models import DocumentType, FinanceDocument
from apps.identity.policy import Permission, has_permission
from apps.identity.services import set_active_context

from ..services import (
    DuplicateDocumentError,
    create_finance_document_with_metadata,
    update_finance_document_metadata,
)
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


def _require_view(context):
    if not has_permission(context.membership, Permission.VIEW_FINANCE):
        raise PermissionDenied("You cannot view finance documents.")


def _require_manage(context):
    if not has_permission(context.membership, Permission.MANAGE_FINANCE_DOCUMENTS):
        raise PermissionDenied("You cannot manage finance documents.")


def _document_queryset(context):
    return (
        FinanceDocument.objects.filter(legal_entity=context.legal_entity)
        .select_related(
            "uploaded_by",
            "integrity_metadata",
            "vendor",
            "service",
            "service_account",
            "subscription",
            "expense",
            "income",
            "reimbursement",
            "transfer",
            "founder_funding",
        )
        .order_by("-document_date", "-created_at")
    )


def _get_document(context, object_id):
    document = _document_queryset(context).filter(id=object_id).first()
    if document is None:
        raise ValidationError("Document does not exist in the active legal entity.")
    if document.document_type == DocumentType.PAYSLIP and not has_permission(
        context.membership, Permission.VIEW_SENSITIVE_FINANCE_DOCUMENTS
    ):
        raise PermissionDenied("You cannot access confidential payroll documents.")
    return document


def _filtered_documents(request, context):
    queryset = _document_queryset(context)
    if not has_permission(context.membership, Permission.VIEW_SENSITIVE_FINANCE_DOCUMENTS):
        queryset = queryset.exclude(document_type=DocumentType.PAYSLIP)
    filters = {
        "vendor": "vendor_id",
        "service": "service_id",
        "service_account": "service_account_id",
        "subscription": "subscription_id",
        "document_type": "document_type",
    }
    for parameter, field in filters.items():
        value = request.query_params.get(parameter)
        if value:
            queryset = queryset.filter(**{field: value})

    year = request.query_params.get("year")
    month = request.query_params.get("month")
    if year:
        queryset = queryset.filter(document_date__year=year)
    if month:
        queryset = queryset.filter(document_date__month=month)
    if request.query_params.get("unassigned") == "1":
        queryset = queryset.filter(
            vendor__isnull=True,
            subscription__isnull=True,
            expense__isnull=True,
            income__isnull=True,
            reimbursement__isnull=True,
            transfer__isnull=True,
            founder_funding__isnull=True,
        )

    search = request.query_params.get("q", "").strip()
    if search:
        queryset = queryset.filter(
            Q(original_name__icontains=search)
            | Q(standardized_name__icontains=search)
            | Q(reference__icontains=search)
            | Q(vendor__name__icontains=search)
            | Q(service__name__icontains=search)
            | Q(service_account__alias__icontains=search)
            | Q(subscription__name__icontains=search)
        )
    return queryset


class FinanceDocumentListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = _filtered_documents(request, context)
        return Response(FinanceDocumentIntegritySerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        _require_manage(context)
        serializer = FinanceDocumentIntegritySerializer(
            data=request.data,
            context={"legal_entity": context.legal_entity},
        )
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data[
            "document_type"
        ] == DocumentType.PAYSLIP and not has_permission(
            context.membership, Permission.VIEW_SENSITIVE_FINANCE_DOCUMENTS
        ):
            raise PermissionDenied("You cannot upload confidential payroll documents.")
        try:
            document = create_finance_document_with_metadata(
                legal_entity=context.legal_entity,
                uploaded_by=request.user,
                validated_data=serializer.validated_data,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        except DuplicateDocumentError as exc:
            return Response(
                {
                    "detail": "This exact file already exists in the document library.",
                    "duplicate_document_id": str(exc.document.id),
                    "duplicate_name": exc.document.standardized_name or exc.document.original_name,
                },
                status=status.HTTP_409_CONFLICT,
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
                "standardized_name": document.standardized_name,
                "document_type": document.document_type,
                "document_date": document.document_date.isoformat(),
                "checksum_sha256": document.integrity_metadata.checksum_sha256,
            },
            request=request,
        )
        document = _get_document(context, document.id)
        return Response(
            FinanceDocumentIntegritySerializer(document).data,
            status=status.HTTP_201_CREATED,
        )


class FinanceDocumentDetailView(APIView):
    def get(self, request, object_id):
        context = _context(request)
        _require_view(context)
        return Response(FinanceDocumentIntegritySerializer(_get_document(context, object_id)).data)

    def patch(self, request, object_id):
        context = _context(request)
        _require_manage(context)
        document = _get_document(context, object_id)
        serializer = FinanceDocumentIntegritySerializer(
            document,
            data=request.data,
            partial=True,
            context={"legal_entity": context.legal_entity},
        )
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get(
            "document_type"
        ) == DocumentType.PAYSLIP and not has_permission(
            context.membership, Permission.VIEW_SENSITIVE_FINANCE_DOCUMENTS
        ):
            raise PermissionDenied("You cannot classify a document as confidential payroll.")
        document = update_finance_document_metadata(
            document=document,
            validated_data=serializer.validated_data,
        )
        record_audit_event(
            actor=request.user,
            organization=context.membership.organization,
            legal_entity=context.legal_entity,
            action="documents.finance_document_updated",
            object_type="FinanceDocument",
            object_id=document.id,
            new_state={
                "standardized_name": document.standardized_name,
                "document_type": document.document_type,
                "document_date": document.document_date.isoformat(),
                "reference": document.reference,
                "vendor_id": str(document.vendor_id) if document.vendor_id else None,
                "service_id": str(document.service_id) if document.service_id else None,
                "service_account_id": (
                    str(document.service_account_id) if document.service_account_id else None
                ),
                "subscription_id": (
                    str(document.subscription_id) if document.subscription_id else None
                ),
            },
            request=request,
        )
        return Response(
            FinanceDocumentIntegritySerializer(_get_document(context, document.id)).data
        )


class FinanceDocumentContentView(APIView):
    def get(self, request, object_id):
        context = _context(request)
        _require_view(context)
        document = _get_document(context, object_id)
        disposition = request.query_params.get("disposition", "inline")
        naming = request.query_params.get("name", "standard")
        if disposition not in {"inline", "attachment"}:
            raise ValidationError("disposition must be inline or attachment.")
        if naming not in {"standard", "original"}:
            raise ValidationError("name must be standard or original.")

        filename = (
            document.original_name
            if naming == "original"
            else document.standardized_name or document.original_name
        )
        try:
            mime_type = document.integrity_metadata.mime_type
        except ObjectDoesNotExist:
            mime_type = (
                mimetypes.guess_type(document.original_name)[0] or "application/octet-stream"
            )
        document.file.open("rb")
        response = FileResponse(
            document.file,
            as_attachment=disposition == "attachment",
            filename=filename,
            content_type=mime_type,
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"

        if disposition == "attachment":
            record_audit_event(
                actor=request.user,
                organization=context.membership.organization,
                legal_entity=context.legal_entity,
                action="documents.finance_document_downloaded",
                object_type="FinanceDocument",
                object_id=document.id,
                new_state={"filename": filename, "naming": naming},
                request=request,
            )
        return response
