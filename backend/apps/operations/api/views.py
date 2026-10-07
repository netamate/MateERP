from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.policy import Permission, has_permission
from apps.identity.services import set_active_context

from ..models import (
    BillingPayment,
    ServiceAccount,
    Subscription,
    SubscriptionBillingPeriod,
    SubscriptionInvoice,
    VendorService,
)
from ..selectors import billing_dashboard, renewal_calendar
from ..services import (
    audit_operations_change,
    create_billing_payment,
    create_billing_period,
    create_subscription_invoice,
    record_subscription_payment,
    replace_billing_payment_allocations,
    update_billing_period,
    update_subscription_invoice,
    void_subscription_invoice,
)
from .serializers import (
    BillingAllocationsSerializer,
    BillingPaymentSerializer,
    RenewalQuerySerializer,
    ServiceAccountSerializer,
    SubscriptionBillingPeriodSerializer,
    SubscriptionInvoiceSerializer,
    SubscriptionPaymentActionSerializer,
    SubscriptionPaymentSerializer,
    SubscriptionSerializer,
    VendorServiceSerializer,
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
        .select_related("vendor", "service", "service_account")
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


def _get_service(context, object_id):
    item = (
        VendorService.objects.filter(id=object_id, legal_entity=context.legal_entity)
        .select_related("vendor")
        .first()
    )
    if item is None:
        raise ValidationError("Service not found in the active legal entity.")
    return item


def _get_service_account(context, object_id):
    item = (
        ServiceAccount.objects.filter(id=object_id, legal_entity=context.legal_entity)
        .select_related("service", "service__vendor")
        .first()
    )
    if item is None:
        raise ValidationError("Service account not found in the active legal entity.")
    return item


class VendorServiceListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        services = VendorService.objects.filter(legal_entity=context.legal_entity).select_related(
            "vendor"
        )
        return Response(VendorServiceSerializer(services, many=True).data)

    def post(self, request):
        context = _context(request)
        _require_manage(context)
        serializer = VendorServiceSerializer(
            data=request.data, context={"legal_entity": context.legal_entity}
        )
        obj = _create_master(
            request,
            context,
            serializer,
            object_type="VendorService",
            action="operations.vendor_service_created",
        )
        return Response(VendorServiceSerializer(obj).data, status=status.HTTP_201_CREATED)


class VendorServiceDetailView(APIView):
    def patch(self, request, object_id):
        context = _context(request)
        _require_manage(context)
        obj = _get_service(context, object_id)
        serializer = VendorServiceSerializer(
            obj,
            data=request.data,
            partial=True,
            context={"legal_entity": context.legal_entity},
        )
        obj = _update_master(
            request,
            context,
            obj,
            serializer,
            object_type="VendorService",
            action="operations.vendor_service_updated",
        )
        return Response(VendorServiceSerializer(obj).data)


class ServiceAccountListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        accounts = ServiceAccount.objects.filter(legal_entity=context.legal_entity).select_related(
            "service", "service__vendor"
        )
        return Response(ServiceAccountSerializer(accounts, many=True).data)

    def post(self, request):
        context = _context(request)
        _require_manage(context)
        serializer = ServiceAccountSerializer(
            data=request.data, context={"legal_entity": context.legal_entity}
        )
        obj = _create_master(
            request,
            context,
            serializer,
            object_type="ServiceAccount",
            action="operations.service_account_created",
        )
        return Response(ServiceAccountSerializer(obj).data, status=status.HTTP_201_CREATED)


class ServiceAccountDetailView(APIView):
    def patch(self, request, object_id):
        context = _context(request)
        _require_manage(context)
        obj = _get_service_account(context, object_id)
        serializer = ServiceAccountSerializer(
            obj,
            data=request.data,
            partial=True,
            context={"legal_entity": context.legal_entity},
        )
        obj = _update_master(
            request,
            context,
            obj,
            serializer,
            object_type="ServiceAccount",
            action="operations.service_account_updated",
        )
        return Response(ServiceAccountSerializer(obj).data)


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
        serializer = SubscriptionSerializer(
            data=request.data, context={"legal_entity": context.legal_entity}
        )
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
        serializer = SubscriptionSerializer(
            obj,
            data=request.data,
            partial=True,
            context={"legal_entity": context.legal_entity},
        )
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



def _get_billing_period(context, object_id):
    period = (
        SubscriptionBillingPeriod.objects.filter(
            id=object_id,
            legal_entity=context.legal_entity,
        )
        .select_related(
            "subscription",
            "subscription__vendor",
            "subscription__service",
            "subscription__service_account",
        )
        .prefetch_related("invoices__payment_allocations")
        .first()
    )
    if period is None:
        raise ValidationError("Billing period does not exist in the active legal entity.")
    return period


def _get_subscription_invoice(context, object_id):
    invoice = (
        SubscriptionInvoice.objects.filter(
            id=object_id,
            legal_entity=context.legal_entity,
        )
        .select_related(
            "billing_period",
            "billing_period__subscription",
            "vendor",
            "document",
            "expense",
        )
        .prefetch_related("payment_allocations")
        .first()
    )
    if invoice is None:
        raise ValidationError("Invoice does not exist in the active legal entity.")
    return invoice


def _get_billing_payment(context, object_id):
    payment = (
        BillingPayment.objects.filter(
            id=object_id,
            legal_entity=context.legal_entity,
        )
        .select_related(
            "subscription",
            "financial_account",
            "expense_payment",
        )
        .prefetch_related("allocations", "allocations__invoice")
        .first()
    )
    if payment is None:
        raise ValidationError("Billing payment does not exist in the active legal entity.")
    return payment


class BillingDashboardView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        return Response(billing_dashboard(context.legal_entity))


class BillingPeriodListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = (
            SubscriptionBillingPeriod.objects.filter(legal_entity=context.legal_entity)
            .select_related(
                "subscription",
                "subscription__vendor",
                "subscription__service",
                "subscription__service_account",
            )
            .prefetch_related("invoices__payment_allocations")
        )
        subscription_id = request.query_params.get("subscription")
        if subscription_id:
            queryset = queryset.filter(subscription_id=subscription_id)
        return Response(
            SubscriptionBillingPeriodSerializer(queryset, many=True).data
        )

    def post(self, request):
        context = _context(request)
        _require_manage(context)
        serializer = SubscriptionBillingPeriodSerializer(
            data=request.data,
            context={"legal_entity": context.legal_entity},
        )
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        subscription = data.pop("subscription")
        period = create_billing_period(
            membership=context.membership,
            subscription=subscription,
            request=request,
            **data,
        )
        period = _get_billing_period(context, period.id)
        return Response(
            SubscriptionBillingPeriodSerializer(period).data,
            status=status.HTTP_201_CREATED,
        )


class BillingPeriodDetailView(APIView):
    def get(self, request, object_id):
        context = _context(request)
        _require_view(context)
        return Response(
            SubscriptionBillingPeriodSerializer(
                _get_billing_period(context, object_id)
            ).data
        )

    def patch(self, request, object_id):
        context = _context(request)
        _require_manage(context)
        period = _get_billing_period(context, object_id)
        serializer = SubscriptionBillingPeriodSerializer(
            period,
            data=request.data,
            partial=True,
            context={"legal_entity": context.legal_entity},
        )
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data.pop("subscription", None)
        period = update_billing_period(
            membership=context.membership,
            period=period,
            data=data,
            request=request,
        )
        return Response(
            SubscriptionBillingPeriodSerializer(
                _get_billing_period(context, period.id)
            ).data
        )


class SubscriptionInvoiceListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = (
            SubscriptionInvoice.objects.filter(legal_entity=context.legal_entity)
            .select_related(
                "billing_period",
                "billing_period__subscription",
                "vendor",
                "document",
                "expense",
            )
            .prefetch_related("payment_allocations")
        )
        period_id = request.query_params.get("billing_period")
        subscription_id = request.query_params.get("subscription")
        if period_id:
            queryset = queryset.filter(billing_period_id=period_id)
        if subscription_id:
            queryset = queryset.filter(
                billing_period__subscription_id=subscription_id
            )
        return Response(SubscriptionInvoiceSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        _require_manage(context)
        serializer = SubscriptionInvoiceSerializer(
            data=request.data,
            context={"legal_entity": context.legal_entity},
        )
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        billing_period = data.pop("billing_period")
        try:
            invoice = create_subscription_invoice(
                membership=context.membership,
                billing_period=billing_period,
                request=request,
                **data,
            )
        except IntegrityError as exc:
            raise ValidationError(
                {"invoice_number": "This vendor invoice number is already recorded."}
            ) from exc
        invoice = _get_subscription_invoice(context, invoice.id)
        return Response(
            SubscriptionInvoiceSerializer(invoice).data,
            status=status.HTTP_201_CREATED,
        )


class SubscriptionInvoiceDetailView(APIView):
    def get(self, request, object_id):
        context = _context(request)
        _require_view(context)
        return Response(
            SubscriptionInvoiceSerializer(
                _get_subscription_invoice(context, object_id)
            ).data
        )

    def patch(self, request, object_id):
        context = _context(request)
        _require_manage(context)
        invoice = _get_subscription_invoice(context, object_id)
        serializer = SubscriptionInvoiceSerializer(
            invoice,
            data=request.data,
            partial=True,
            context={"legal_entity": context.legal_entity},
        )
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data.pop("billing_period", None)
        data.pop("vendor", None)
        try:
            invoice = update_subscription_invoice(
                membership=context.membership,
                invoice=invoice,
                data=data,
                request=request,
            )
        except IntegrityError as exc:
            raise ValidationError(
                {"invoice_number": "This vendor invoice number is already recorded."}
            ) from exc
        return Response(
            SubscriptionInvoiceSerializer(
                _get_subscription_invoice(context, invoice.id)
            ).data
        )


class SubscriptionInvoiceVoidView(APIView):
    def post(self, request, object_id):
        context = _context(request)
        _require_manage(context)
        invoice = void_subscription_invoice(
            membership=context.membership,
            invoice=_get_subscription_invoice(context, object_id),
            request=request,
        )
        return Response(
            SubscriptionInvoiceSerializer(
                _get_subscription_invoice(context, invoice.id)
            ).data
        )


class BillingPaymentListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = (
            BillingPayment.objects.filter(legal_entity=context.legal_entity)
            .select_related(
                "subscription",
                "financial_account",
                "expense_payment",
            )
            .prefetch_related("allocations", "allocations__invoice")
        )
        subscription_id = request.query_params.get("subscription")
        if subscription_id:
            queryset = queryset.filter(subscription_id=subscription_id)
        return Response(BillingPaymentSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        _require_manage(context)
        serializer = BillingPaymentSerializer(
            data=request.data,
            context={"legal_entity": context.legal_entity},
        )
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        subscription = data.pop("subscription")
        payment = create_billing_payment(
            membership=context.membership,
            subscription=subscription,
            request=request,
            **data,
        )
        return Response(
            BillingPaymentSerializer(
                _get_billing_payment(context, payment.id)
            ).data,
            status=status.HTTP_201_CREATED,
        )


class BillingPaymentDetailView(APIView):
    def get(self, request, object_id):
        context = _context(request)
        _require_view(context)
        return Response(
            BillingPaymentSerializer(_get_billing_payment(context, object_id)).data
        )


class BillingPaymentAllocationView(APIView):
    def put(self, request, object_id):
        context = _context(request)
        _require_manage(context)
        payment = _get_billing_payment(context, object_id)
        serializer = BillingAllocationsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        allocations = serializer.validated_data["allocations"]
        for item in allocations:
            if item["invoice"].legal_entity_id != context.legal_entity.id:
                raise ValidationError(
                    {"allocations": "An invoice belongs to another legal entity."}
                )
        payment = replace_billing_payment_allocations(
            membership=context.membership,
            payment=payment,
            allocations=allocations,
            request=request,
        )
        return Response(
            BillingPaymentSerializer(
                _get_billing_payment(context, payment.id)
            ).data
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
