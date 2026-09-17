from django.urls import path

from .views import (
    ApprovalActionListView,
    ExpenseListCreateView,
    ExpensePaymentCreateView,
    ExpenseWorkflowView,
    FinanceDocumentListCreateView,
    FinancialAccountListCreateView,
    FinancialAccountTransactionView,
    FounderFundingListCreateView,
    IncomeListCreateView,
    ReimbursementListCreateView,
    ReimbursementPaymentCreateView,
    ReimbursementWorkflowView,
    TransferListCreateView,
    VendorListCreateView,
)

urlpatterns = [
    path("finance/vendors/", VendorListCreateView.as_view(), name="finance-vendors"),
    path(
        "finance/accounts/",
        FinancialAccountListCreateView.as_view(),
        name="finance-accounts",
    ),
    path(
        "finance/accounts/<uuid:account_id>/transactions/",
        FinancialAccountTransactionView.as_view(),
        name="finance-account-transactions",
    ),
    path("finance/expenses/", ExpenseListCreateView.as_view(), name="finance-expenses"),
    path(
        "finance/expenses/<uuid:expense_id>/workflow/",
        ExpenseWorkflowView.as_view(),
        name="finance-expense-workflow",
    ),
    path(
        "finance/expenses/<uuid:expense_id>/payments/",
        ExpensePaymentCreateView.as_view(),
        name="finance-expense-payment",
    ),
    path("finance/income/", IncomeListCreateView.as_view(), name="finance-income"),
    path("finance/transfers/", TransferListCreateView.as_view(), name="finance-transfers"),
    path(
        "finance/founder-funding/",
        FounderFundingListCreateView.as_view(),
        name="finance-founder-funding",
    ),
    path(
        "finance/reimbursements/",
        ReimbursementListCreateView.as_view(),
        name="finance-reimbursements",
    ),
    path(
        "finance/reimbursements/<uuid:reimbursement_id>/workflow/",
        ReimbursementWorkflowView.as_view(),
        name="finance-reimbursement-workflow",
    ),
    path(
        "finance/reimbursements/<uuid:reimbursement_id>/payments/",
        ReimbursementPaymentCreateView.as_view(),
        name="finance-reimbursement-payment",
    ),
    path(
        "finance/approvals/",
        ApprovalActionListView.as_view(),
        name="finance-approvals",
    ),
    path(
        "finance/documents/",
        FinanceDocumentListCreateView.as_view(),
        name="finance-documents",
    ),
]
