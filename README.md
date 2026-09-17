# MateERP

MateERP is NetaMate Solutions' enterprise financial and business operations ERP.

This repository is the production monorepo. The current development stage is **Phase 2: Project Bootstrap & Engineering Foundation**.

## Repository structure

```text
MateERP/
├── backend/        Django + Django REST Framework API
├── frontend/       Next.js App Router frontend
├── docs/           Architecture and development documentation
├── deploy/         Deployment assets added as Phase 2/9 work requires
├── .github/        CI workflows
├── compose.yaml    Local Docker development stack
└── README.md
```

## Phase 2 boundaries

Phase 2 establishes the engineering foundation only. It does not implement the accounting engine, organization/security domain, finance operations, or other later-phase business modules.

## Local development

### Prerequisites

- Docker Desktop with Docker Compose v2
- Git

### Start

1. Copy `.env.example` to `.env`.
2. Start the stack:

```powershell
docker compose up --build
```

3. Open:

- Frontend: http://localhost:3000
- API health: http://localhost:8000/api/v1/health/
- OpenAPI schema: http://localhost:8000/api/schema/
- Swagger UI: http://localhost:8000/api/docs/

See `docs/development.md` for non-Docker commands and quality checks.
