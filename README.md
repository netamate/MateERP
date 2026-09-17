# MateERP

MateERP is NetaMate Solutions' enterprise financial and business operations ERP.

The production monorepo is currently in **Phase 3: Identity, Organization & Security Core**.

## Repository structure

```text
MateERP/
├── backend/        Django + Django REST Framework API
├── frontend/       Next.js App Router frontend
├── docs/           Architecture, security, and development documentation
├── deploy/         Deployment assets
├── .github/        CI workflows
├── compose.yaml    Local Docker development stack
└── README.md
```

## Phase 3 scope

The current codebase establishes:

- UUID email-based user identities
- organizations and legal entities
- organization memberships and legal-entity access scope
- centralized RBAC policy
- Django session authentication and CSRF protection
- server-side active organization/legal-entity context
- append-only audit events and request IDs
- secure initial instance bootstrap
- authenticated frontend shell and context selectors

Financial accounting and operational finance modules are intentionally not implemented yet.

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

See `docs/development.md`, `docs/security.md`, and `docs/phase-3.md`.
