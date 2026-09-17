# Phase 7 — Operations, Planning & Asset Management

Phase 7 turns recurring operational obligations and planning dimensions into first-class MateERP domains without duplicating accounting truth.

## Operations

The `operations` Django app owns:

- subscriptions and recurring obligations
- domains, ownership metadata, expiry, renewal cost, registrar, DNS provider, product association, and auto-renew status
- immutable domain renewal history
- infrastructure assets such as VPS, hosting, cloud, storage, CDN, backup, email infrastructure, monitoring, and other services
- a derived renewal calendar that aggregates active subscriptions, domains, and infrastructure records

The renewal calendar is a read model only. It does not create a separate renewal source of truth.

A domain renewal may optionally generate a draft `Expense` through the existing finance service layer. The operational record and financial record remain separate.

## Planning

The `planning` Django app owns:

- cost centers
- products
- projects
- amount-based expense allocations
- budgets and budget lines
- budget-versus-actual reporting

Cost Centers, Products, and Projects remain separate dimensions. Projects may optionally reference a Product.

Expense allocations store authoritative amounts. Percentage splits are intentionally not stored as accounting truth. Allocation changes are restricted to draft expenses and are replaced atomically.

Budget actuals are calculated from real posted financial data:

- an account-only budget line reads posted journal lines
- a budget line with planning dimensions reads posted expense allocations

Users cannot manually edit an `actual` budget value.

## REST API

All endpoints remain under `/api/v1/` and use the existing session-authentication, CSRF, legal-entity scope, and RBAC foundations.

Operations:

- `GET/POST /api/v1/operations/subscriptions/`
- `GET/PATCH /api/v1/operations/subscriptions/{id}/`
- `GET/POST /api/v1/operations/domains/`
- `GET/PATCH /api/v1/operations/domains/{id}/`
- `POST /api/v1/operations/domains/{id}/renew/`
- `GET /api/v1/operations/domains/{id}/renewals/`
- `GET/POST /api/v1/operations/infrastructure/`
- `GET/PATCH /api/v1/operations/infrastructure/{id}/`
- `GET /api/v1/operations/renewals/`

Planning:

- `GET/POST /api/v1/planning/cost-centers/`
- `PATCH /api/v1/planning/cost-centers/{id}/`
- `GET/POST /api/v1/planning/products/`
- `PATCH /api/v1/planning/products/{id}/`
- `GET/POST /api/v1/planning/projects/`
- `PATCH /api/v1/planning/projects/{id}/`
- `GET/PUT /api/v1/planning/expenses/{expense_id}/allocations/`
- `GET/POST /api/v1/planning/budgets/`
- `GET/PATCH /api/v1/planning/budgets/{id}/`
- `GET/POST /api/v1/planning/budgets/{id}/lines/`
- `GET /api/v1/planning/budgets/{id}/actuals/`

## Frontend

The Phase 6 application shell now exposes real Operations and Planning navigation. The production Next.js UI includes:

- subscription management
- domain management and renewal history
- domain renewal workflow with optional draft expense generation
- infrastructure asset management
- aggregated renewal calendar
- cost center, product, and project management
- budget lifecycle, budget lines, and ledger-derived actuals
- multi-line expense allocation across cost centers, products, and projects

The frontend retains MateERP's zero-radius enterprise design system and the existing loading, empty, error, and permission-state patterns.

## Phase boundary

Phase 7 does not introduce payroll, employee HR records, external registrar APIs, automatic renewal purchasing, bank feeds, or background workers. Those remain future capabilities unless a later phase explicitly adds them.
