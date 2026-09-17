# Phase 5 — Core Finance Operations

Phase 5 turns the Phase 4 accounting engine into day-to-day company finance workflows.
Operational records are legal-entity scoped and every posted financial event is represented
by balanced, immutable journal entries in the accounting module.

## Delivered scope

- Vendors with default expense and payable account references.
- Financial accounts backed by Chart of Accounts ledger accounts.
- Financial account transaction history derived from posted journal lines.
- Expense draft, submit, approve, reject, accrual, partial payment, and full payment flows.
- Income recording into a financial account and revenue account.
- Same-entity financial account transfers with base-currency balancing.
- Founder contributions and founder loans with equity/liability counter accounts.
- Reimbursements with submit, approve, reject, accrual, and payment flows.
- Receipt, invoice, bill, statement, and supporting document uploads.
- Append-only workflow action history for expense and reimbursement approvals.
- Finance-specific RBAC permissions integrated with Phase 3 membership roles.
- Audit events for material finance operations.

## Accounting rules

Operational finance never writes balances directly. Services call the Phase 4 journal engine,
which enforces legal-entity scope, open fiscal periods, double-entry balance, immutable posted
entries, and base-currency calculations.

Expense approval accrues expense/tax against a payable liability. Expense payment clears the
liability against a financial account. Reimbursements use the same accrual/payment pattern.
Income debits the receiving financial account and credits revenue. Transfers debit the
destination ledger account and credit the source. Founder contributions credit equity while
founder loans credit a liability account.

## Phase boundary

Phase 5 does not introduce payroll, CRM, Helpdesk, project management, HRIS, inventory,
warehouse management, or tax filing. Later phases may build richer AP/AR, reconciliation,
automation, budgeting, or operational modules on this foundation.
