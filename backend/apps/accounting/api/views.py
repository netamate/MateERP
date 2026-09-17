from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import Account, ExchangeRate, FiscalPeriod, JournalEntry, TaxCode
from apps.accounting.selectors import (
    balance_sheet,
    cash_flow_summary,
    profit_and_loss,
    trial_balance,
)
from apps.accounting.services import close_period, create_journal, post_journal, reverse_journal
from apps.identity.policy import Permission, has_permission
from apps.identity.services import set_active_context

from .serializers import (
    AccountSerializer,
    ExchangeRateSerializer,
    FiscalPeriodSerializer,
    JournalCreateSerializer,
    JournalEntrySerializer,
    JournalReverseSerializer,
    PeriodCloseSerializer,
    TaxCodeSerializer,
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
    if not has_permission(context.membership, Permission.VIEW_ACCOUNTING):
        raise PermissionDenied("You do not have permission to view accounting data.")


class AccountListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = Account.objects.filter(legal_entity=context.legal_entity)
        return Response(AccountSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        if not has_permission(context.membership, Permission.EDIT_CHART_OF_ACCOUNTS):
            raise PermissionDenied("You cannot edit the Chart of Accounts.")
        serializer = AccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = serializer.save(legal_entity=context.legal_entity)
        return Response(AccountSerializer(account).data, status=status.HTTP_201_CREATED)


class FiscalPeriodListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = FiscalPeriod.objects.filter(legal_entity=context.legal_entity)
        return Response(FiscalPeriodSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        if not has_permission(context.membership, Permission.CLOSE_PERIOD):
            raise PermissionDenied("You cannot manage fiscal periods.")
        serializer = FiscalPeriodSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        period = serializer.save(legal_entity=context.legal_entity)
        return Response(FiscalPeriodSerializer(period).data, status=status.HTTP_201_CREATED)


class PeriodCloseView(APIView):
    def post(self, request, period_id):
        context = _context(request)
        serializer = PeriodCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        period = FiscalPeriod.objects.filter(
            id=period_id,
            legal_entity=context.legal_entity,
        ).first()
        if period is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        close_period(
            membership=context.membership,
            period=period,
            request=request,
            **serializer.validated_data,
        )
        return Response(FiscalPeriodSerializer(period).data)


class JournalListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = JournalEntry.objects.filter(legal_entity=context.legal_entity).prefetch_related(
            "lines"
        )
        return Response(JournalEntrySerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        serializer = JournalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        journal = create_journal(
            membership=context.membership,
            legal_entity=context.legal_entity,
            request=request,
            **serializer.validated_data,
        )
        return Response(JournalEntrySerializer(journal).data, status=status.HTTP_201_CREATED)


class JournalPostView(APIView):
    def post(self, request, journal_id):
        context = _context(request)
        journal = JournalEntry.objects.filter(
            id=journal_id,
            legal_entity=context.legal_entity,
        ).first()
        if journal is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        journal = post_journal(
            membership=context.membership,
            journal=journal,
            request=request,
        )
        return Response(JournalEntrySerializer(journal).data)


class JournalReverseView(APIView):
    def post(self, request, journal_id):
        context = _context(request)
        journal = JournalEntry.objects.filter(
            id=journal_id,
            legal_entity=context.legal_entity,
        ).first()
        if journal is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = JournalReverseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reversal = reverse_journal(
            membership=context.membership,
            journal=journal,
            request=request,
            **serializer.validated_data,
        )
        return Response(JournalEntrySerializer(reversal).data, status=status.HTTP_201_CREATED)


class TaxCodeListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = TaxCode.objects.filter(legal_entity=context.legal_entity)
        return Response(TaxCodeSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        if not has_permission(context.membership, Permission.MANAGE_TAX_CONFIG):
            raise PermissionDenied("You cannot manage tax configuration.")
        serializer = TaxCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tax_code = serializer.save(legal_entity=context.legal_entity)
        return Response(TaxCodeSerializer(tax_code).data, status=status.HTTP_201_CREATED)


class ExchangeRateListCreateView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        queryset = ExchangeRate.objects.filter(legal_entity=context.legal_entity)
        return Response(ExchangeRateSerializer(queryset, many=True).data)

    def post(self, request):
        context = _context(request)
        if not has_permission(context.membership, Permission.MANAGE_FX_RATES):
            raise PermissionDenied("You cannot manage exchange rates.")
        serializer = ExchangeRateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rate = serializer.save(legal_entity=context.legal_entity)
        return Response(ExchangeRateSerializer(rate).data, status=status.HTTP_201_CREATED)


class TrialBalanceView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        return Response(
            trial_balance(
                context.legal_entity,
                start_date=request.query_params.get("start_date"),
                end_date=request.query_params.get("end_date"),
            )
        )


class ProfitLossView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        if not start_date or not end_date:
            raise ValidationError("start_date and end_date are required.")
        report = profit_and_loss(
            context.legal_entity,
            start_date=start_date,
            end_date=end_date,
        )
        return Response(report)


class BalanceSheetView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        as_of = request.query_params.get("as_of")
        if not as_of:
            raise ValidationError("as_of is required.")
        return Response(balance_sheet(context.legal_entity, as_of=as_of))


class CashFlowView(APIView):
    def get(self, request):
        context = _context(request)
        _require_view(context)
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        if not start_date or not end_date:
            raise ValidationError("start_date and end_date are required.")
        report = cash_flow_summary(
            context.legal_entity,
            start_date=start_date,
            end_date=end_date,
        )
        return Response(report)
