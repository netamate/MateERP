from django.urls import path

from .views import (
    AccountBalanceReportView,
    CostCenterSpendView,
    CurrencyExposureView,
    ExpenseReportView,
    FinancialOverviewView,
    FounderCapitalView,
    OperationsCostExportView,
    OperationsCostIntelligenceView,
    ProductCostView,
    RevenueReportView,
    VendorSpendView,
)

urlpatterns = [
    path("reporting/overview/", FinancialOverviewView.as_view(), name="reporting-overview"),
    path("reporting/expenses/", ExpenseReportView.as_view(), name="reporting-expenses"),
    path("reporting/revenue/", RevenueReportView.as_view(), name="reporting-revenue"),
    path("reporting/vendor-spend/", VendorSpendView.as_view(), name="reporting-vendor-spend"),
    path("reporting/product-cost/", ProductCostView.as_view(), name="reporting-product-cost"),
    path(
        "reporting/cost-center-spend/",
        CostCenterSpendView.as_view(),
        name="reporting-cost-center-spend",
    ),
    path(
        "reporting/account-balances/",
        AccountBalanceReportView.as_view(),
        name="reporting-account-balances",
    ),
    path(
        "reporting/currency-exposure/",
        CurrencyExposureView.as_view(),
        name="reporting-currency-exposure",
    ),
    path(
        "reporting/founder-capital/",
        FounderCapitalView.as_view(),
        name="reporting-founder-capital",
    ),
    path(
        "reporting/cost-intelligence/",
        OperationsCostIntelligenceView.as_view(),
        name="reporting-cost-intelligence",
    ),
    path(
        "reporting/cost-intelligence/export/",
        OperationsCostExportView.as_view(),
        name="reporting-cost-intelligence-export",
    ),
]
