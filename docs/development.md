# Development Guide

## Environment strategy

MateERP uses environment variables for runtime configuration. Secrets must not be committed.

Local development uses the root `.env` file based on `.env.example`.

Production configuration will be injected by the deployment environment and GitHub Actions. Production secrets must live in the approved secret stores, not in repository files.

## Docker development

Run from the repository root on the Windows 11 workstation in PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Stop without deleting persistent PostgreSQL data:

```powershell
docker compose down
```

Do not use `docker compose down -v` unless the development database volume is intentionally being destroyed.

## Backend without Docker

Run from `backend/` on the Windows 11 workstation in PowerShell. A PostgreSQL instance and a valid `DATABASE_URL` are required.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
python manage.py migrate
python manage.py runserver
```

Quality checks:

```powershell
ruff check .
ruff format --check .
pytest
python manage.py spectacular --validate --file schema.yml
```

## Frontend without Docker

Run from `frontend/` on the Windows 11 workstation in PowerShell:

```powershell
npm install
npm run dev
```

Quality checks:

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
```

The first successful frontend install should generate `frontend/package-lock.json`. Commit that lockfile, then CI can be tightened from `npm install` to `npm ci`.

## API convention

Application REST endpoints live under `/api/v1/`.

OpenAPI endpoints are infrastructure endpoints and currently live at:

- `/api/schema/`
- `/api/docs/`

## Current Phase 2 rule

Do not add Phase 3+ domain models until the bootstrap foundation is stable and the Phase 2 checks are green.
