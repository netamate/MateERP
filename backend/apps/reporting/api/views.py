import csv

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.policy import Permission, has_permission
from apps.identity.services import set_active_context

from ..selectors import (
    account_balances,
    cost_center_spend,
    currency_exposure,
    expense_report,
    financial_overview,
    founder_capital,
    operations_cost_intelligence,
    product_cost,
    revenue_report,
    vendor_spend,
)
from .serializers import AsOfSerializer, ReportRangeSerializer


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


def _require_reports(context):
    if not has_permission(context.membership, Permission.VIEW_REPORTS):
        raise PermissionDenied("You do not have permission to view enterprise reports.")


def _range(request):
    serializer = ReportRangeSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _as_of(request):
    serializer = AsOfSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data.get("as_of")


class FinancialOverviewView(APIView):
    def get(self, request):
        context = _context(request)
        _require_reports(context)
        return Response(financial_overview(context.legal_entity, **_range(request)))


class ExpenseReportView(APIView):
    def get(self, request):
        context = _context(request)
        _require_reports(context)
        return Response(expense_report(context.legal_entity, **_range(request)))


class RevenueReportView(APIView):
    def get(self, request):
        context = _context(request)
        _require_reports(context)
        return Response(revenue_report(context.legal_entity, **_range(request)))


class VendorSpendView(APIView):
    def get(self, request):
        context = _context(request)
        _require_reports(context)
        return Response(vendor_spend(context.legal_entity, **_range(request)))


class ProductCostView(APIView):
    def get(self, request):
        context = _context(request)
        _require_reports(context)
        return Response(product_cost(context.legal_entity, **_range(request)))


class CostCenterSpendView(APIView):
    def get(self, request):
        context = _context(request)
        _require_reports(context)
        return Response(cost_center_spend(context.legal_entity, **_range(request)))


class AccountBalanceReportView(APIView):
    def get(self, request):
        context = _context(request)
        _require_reports(context)
        return Response(account_balances(context.legal_entity, as_of=_as_of(request)))


class CurrencyExposureView(APIView):
    def get(self, request):
        context = _context(request)
        _require_reports(context)
        return Response(currency_exposure(context.legal_entity, as_of=_as_of(request)))


class FounderCapitalView(APIView):
    def get(self, request):
        context = _context(request)
        _require_reports(context)
        return Response(founder_capital(context.legal_entity, **_range(request)))


class OperationsCostIntelligenceView(APIView):
    def get(self, request):
        context = _context(request)
        _require_reports(context)
        return Response(
            operations_cost_intelligence(
                context.legal_entity,
                **_range(request),
            )
        )


class OperationsCostExportView(APIView):
    def get(self, request):
        context = _context(request)
        _require_reports(context)
        data = operations_cost_intelligence(
            context.legal_entity,
            **_range(request),
        )
        section = request.query_params.get("section", "subscriptions")
        sections = {
            "subscriptions": data["subscriptions"],
            "vendors": data["vendors"],
            "monthly": data["monthly_trend"],
        }
        if section not in sections:
            raise ValidationError("section must be one of: subscriptions, vendors, monthly.")
        rows = sections[section]
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="mateerp-{section}-cost-report.csv"'
        )
        if not rows:
            return response
        writer = csv.DictWriter(response, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        return response
