# Phase 4: Financial & Accounting Engine

Phase 4 establishes MateERP's authoritative double-entry accounting core.

## Implemented controls

- Chart of Accounts per legal entity with hierarchical accounts and system/control markers.
- Fiscal periods with open, soft-close, and hard-close states.
- Draft, posted, and reversed journal lifecycle.
- Base-currency balancing before posting.
- Transaction currency and FX rate capture on every journal line.
- Posted journal correction through equal-and-opposite reversal entries.
- Tax-code references with input and output control accounts.
- Exchange-rate master data scoped to the legal entity.
- Trial Balance, Profit & Loss, Balance Sheet, and cash-flow summary derived from posted ledger lines.
- Accounting actions protected by Phase 3 RBAC and legal-entity scope checks.
- Audit events for journal creation, posting, reversal, and fiscal-period close.

## Invariants

1. Every posted journal balances in base currency.
2. Posting is allowed only inside an open fiscal period.
3. Accounts, tax codes, journals, and periods cannot cross legal-entity boundaries.
4. Posted journal lines cannot be edited or deleted.
5. Corrections use reversal entries rather than destructive edits.
6. Financial reports read from posted ledger lines instead of maintaining parallel totals.

Expense, AP, cash-account workflow, recurring cost, subscription, asset, project, and budgeting modules remain later roadmap phases and will post into this accounting engine rather than creating independent financial truth.
