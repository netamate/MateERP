# Phase 6 — Full Production Frontend

Phase 6 replaces the foundation/overview-only UI with the production MateERP browser workspace for capabilities delivered in Phases 3 through 5.

## Design source of truth

The approved `rizwansammo/MateERP-prototype` remains the visual and workflow reference. The production implementation preserves its enterprise financial character while using the approved Next.js/TypeScript architecture rather than copying the prototype JavaScript.

The production UI keeps:

- dark fixed/sidebar navigation and organization/legal-entity context,
- app header, page headers, metric strips, dense financial tables, and settings patterns,
- global Ctrl/Cmd+K navigation search,
- Quick Add actions,
- responsive mobile navigation,
- loading, empty, error, and permission states,
- sharp 90-degree geometry with `--radius: 0px` and no rounded cards/pills,
- border-led hierarchy instead of decorative gradients or consumer-banking visuals.

## Production workspaces

### Overview

- API-backed dashboard using the active legal entity.

### Finance

- ledger-derived financial account transactions,
- vendors,
- tax-aware expense creation,
- expense submit/approve/reject/payment workflow,
- income recording,
- financial-account transfers,
- financial accounts,
- reimbursement submit/approve/reject/payment workflow,
- founder contributions and founder loans,
- finance documents and approval history.

### Accounting and reporting

- Chart of Accounts creation and list,
- manual journal creation,
- journal posting and correct reversal workflow,
- fiscal-period creation and close,
- tax-code configuration,
- dated FX-rate configuration,
- Profit & Loss, Balance Sheet, Cash Flow, and Trial Balance views.

### Administration

- organization/legal-entity/session context,
- membership list,
- role changes,
- legal-entity access scope changes,
- read-only security and organization settings context.

## Data and security architecture

The browser uses same-origin `/api/v1/` calls through the existing Next.js rewrite. Django session authentication and CSRF remain authoritative. TanStack Query owns server-state caching/invalidation. Backend RBAC and legal-entity scoping remain the final permission boundary; frontend permission checks are only presentation controls.

Financial screens do not create parallel balances. Account transactions and reports are derived from posted Phase 4 journals, while Phase 5 operational services continue to create the accounting entries.

## Testing

Phase 6 keeps the existing frontend lint, TypeScript, Vitest, and production-build gates and adds Playwright browser testing. The initial browser smoke test verifies that an anonymous browser reaches the secure MateERP sign-in experience.

## Phase boundary

Phase 6 does not implement Phase 7 operational domains. Subscriptions, domains, infrastructure assets, renewals, budgets, cost centers, products, projects, and cost allocation remain visibly identified as later work rather than being backed by mock production data.
