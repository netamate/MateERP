# Development

## Docker development

**Machine: Windows 11 workstation / PowerShell**

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The development services bind web ports only to loopback:

- Next.js: `127.0.0.1:3000`
- Django: `127.0.0.1:8000`

PostgreSQL is only available on the internal Docker network.

## Initial Phase 3 bootstrap

After migrations have run, set the bootstrap password only in the current environment
and create the first owner, organization, and legal entity.

**Machine: Windows 11 workstation / PowerShell**

```powershell
$env:MATEERP_BOOTSTRAP_PASSWORD = "<local-secret>"
cd backend
python manage.py bootstrap_instance `
  --email owner@example.com `
  --organization "Example Company" `
  --timezone "Asia/Dhaka" `
  --base-currency "USD"
```

When using Docker, execute the same management command inside the backend service and
provide the environment variable without committing it.

## Backend quality checks

**Machine: Windows 11 workstation / PowerShell**

```powershell
cd backend
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
python manage.py migrate
python manage.py makemigrations --check
pytest
python manage.py spectacular --validate --file schema.yml
```

## Frontend quality checks

**Machine: Windows 11 workstation / PowerShell**

```powershell
cd frontend
npm install
npm run lint
npm run typecheck
npm run test
npm run build
```

## Authentication development flow

The browser talks to `/api/` on the Next.js origin. `next.config.ts` proxies those
requests to Django, keeping session cookies same-origin from the browser's perspective.

The sign-in flow first obtains a Django CSRF token, then posts credentials to the
session-authenticated login endpoint. Authentication tokens are never stored in
`localStorage`.

## Database changes

All model changes require committed Django migrations. Before committing, always run:

```powershell
python manage.py makemigrations --check
python manage.py migrate
```

Do not reset or drop development/production databases casually. Never use destructive
volume commands against data that matters.
