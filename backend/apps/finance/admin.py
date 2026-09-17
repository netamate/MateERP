from django.contrib import admin

from .models import (
    ApprovalAction,
    Expense,
    ExpensePayment,
    FinanceDocument,
    FinancialAccount,
    FounderFunding,
    Income,
    Reimbursement,
    ReimbursementPayment,
    Transfer,
    Vendor,
)

admin.site.register(
    [
        Vendor,
        FinancialAccount,
        Expense,
        ExpensePayment,
        Income,
        Transfer,
        FounderFunding,
        Reimbursement,
        ReimbursementPayment,
        ApprovalAction,
        FinanceDocument,
    ]
)
