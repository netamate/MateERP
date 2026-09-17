from django.urls import path

from .views import (
    AccountListCreateView,
    BalanceSheetView,
    CashFlowView,
    ExchangeRateListCreateView,
    FiscalPeriodListCreateView,
    JournalListCreateView,
    JournalPostView,
    JournalReverseView,
    PeriodCloseView,
    ProfitLossView,
    TaxCodeListCreateView,
    TrialBalanceView,
)

urlpatterns = [
    path("accounting/accounts/", AccountListCreateView.as_view(), name="account-list"),
    path("accounting/periods/", FiscalPeriodListCreateView.as_view(), name="period-list"),
    path(
        "accounting/periods/<uuid:period_id>/close/",
        PeriodCloseView.as_view(),
        name="period-close",
    ),
    path("accounting/journals/", JournalListCreateView.as_view(), name="journal-list"),
    path(
        "accounting/journals/<uuid:journal_id>/post/",
        JournalPostView.as_view(),
        name="journal-post",
    ),
    path(
        "accounting/journals/<uuid:journal_id>/reverse/",
        JournalReverseView.as_view(),
        name="journal-reverse",
    ),
    path("accounting/tax-codes/", TaxCodeListCreateView.as_view(), name="tax-code-list"),
    path("accounting/fx-rates/", ExchangeRateListCreateView.as_view(), name="fx-rate-list"),
    path("accounting/reports/trial-balance/", TrialBalanceView.as_view(), name="trial-balance"),
    path("accounting/reports/profit-loss/", ProfitLossView.as_view(), name="profit-loss"),
    path("accounting/reports/balance-sheet/", BalanceSheetView.as_view(), name="balance-sheet"),
    path("accounting/reports/cash-flow/", CashFlowView.as_view(), name="cash-flow"),
]
