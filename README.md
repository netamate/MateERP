# MateERP

MateERP is NetaMate Solutions' enterprise financial and business operations ERP.

The product development roadmap is currently in **Phase 8: Reporting, Audit & Enterprise Hardening**, the final development phase before **Phase 9: Production Deployment & Go-Live**.

## Repository structure

```text
MateERP/
├── backend/        Django + Django REST Framework modular monolith
├── frontend/       Next.js App Router production frontend
├── docs/           Architecture, security, development, and phase documentation
├── deploy/         Deployment assets and production handoff area
├── .github/        CI workflows
├── compose.yaml    Local Docker development stack
└── README.md
```

## Implemented product foundation

MateERP now includes:

- UUID email-based identities, organizations, legal entities, memberships, and scoped RBAC
- secure Django session authentication, CSRF protection, and request IDs
- append-only audit events with a production audit-log workspace
- double-entry accounting, Chart of Accounts, journals, fiscal periods, tax and FX foundations
- Trial Balance, Profit & Loss, Balance Sheet, Cash Flow, and enterprise management reports
- vendors, expenses, payments, income, transfers, financial accounts, reimbursements, and founder funding
- approval workflows and document uploads with SHA-256 integrity metadata
- subscriptions, domains, domain-renewal history, infrastructure assets, and aggregated renewals
- cost centers, products, projects, expense allocations, budgets, and Budget vs Actual
- financial-account reconciliation with immutable completed statements
- targeted in-app renewal and approval notifications
- responsive zero-radius production frontend with command palette and Quick Add
- backend and frontend CI with Ruff, Django migration checks, pytest, OpenAPI validation, ESLint, TypeScript, Vitest, Next.js build, and Playwright

## Final development boundary

Phase 8 closes application development and production hardening. It does **not** deploy MateERP.

The next phase is **Phase 9: Production Deployment & Go-Live**, covering GHCR image delivery, MateServer Docker Compose configuration, production PostgreSQL persistence and backup/restore validation, host-native Nginx, domain/TLS, scheduled maintenance commands, migrations, smoke testing, rollback validation, and go-live.

## Local development

### Prerequisites

- Docker Desktop with Docker Compose v2
- Git

### Start

1. Copy `.env.example` to `.env`.
2. Set local-only development values in `.env`.
3. Start the stack:

```powershell
docker compose up --build
```

4. Bootstrap the first owner and organization from the backend container or a local backend environment. Set `MATEERP_BOOTSTRAP_PASSWORD` first. Never commit that value.
5. Open:

- Frontend: http://localhost:3000
- API health: http://localhost:8000/api/v1/health/
- OpenAPI schema: http://localhost:8000/api/schema/
- Swagger UI: http://localhost:8000/api/docs/

See `docs/development.md`, `docs/security.md`, and the phase documentation under `docs/`.
