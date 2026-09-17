# Phase 9: Production Deployment & Go-Live

Phase 9 deploys the completed MateERP application to MateServer. Application development is complete; this phase is operational deployment, production hardening, validation, backup, rollback, and go-live.

## Production topology

```text
GitHub private repository: netamate/MateERP
        |
        | green CI on main
        v
GitHub Actions Deploy Production
        |
        | builds private SHA-tagged images
        v
GHCR
  ghcr.io/netamate/mateerp-backend:<commit-sha>
  ghcr.io/netamate/mateerp-frontend:<commit-sha>
        |
        | authenticated pull during deployment
        v
MateServer /opt/MateERP
  docker-compose.yml
  .env                       # mode 600, never committed
  data/media/                # persistent private finance uploads
  data/static/               # collected Django static files
  backups/db/                # PostgreSQL native backups
  scripts/
        |
        +-- mateerp_internal bridge network
        |     +-- database:5432, not published
        |     +-- backend:8000
        |     +-- frontend:3000
        |
        +-- 127.0.0.1:8035 -> backend:8000
        +-- 127.0.0.1:3035 -> frontend:3000
        |
        v
host-native Nginx
        |
        v
https://erp.netamate.com
```

## Production domain and ports

The production hostname is `erp.netamate.com`.

MateServer was inspected before assigning ports. The Phase 9 production allocation is:

- backend host binding: `127.0.0.1:8035`
- frontend host binding: `127.0.0.1:3035`
- PostgreSQL: Docker-internal only, no published host port

Do not change these ports without first re-running `ss -tulpn | grep LISTEN` on MateServer and checking existing NetaMate services.

## Production images

Production images are private GHCR packages:

- `ghcr.io/netamate/mateerp-backend:<commit-sha>`
- `ghcr.io/netamate/mateerp-frontend:<commit-sha>`

The deploy workflow also updates the `main` tag, but the production `.env` is pinned to exact commit-SHA tags after every deployment. This makes rollback deterministic.

The repository remains private. GitHub Actions uses its short-lived `GITHUB_TOKEN` to publish and to authenticate MateServer for the deployment pull. The workflow logs MateServer out of GHCR after the pull completes.

## GitHub Actions

`CI` remains the required application quality gate and now also builds both production Dockerfiles without pushing them.

`Deploy Production` runs after a successful `CI` workflow on `main`:

1. Resolve the exact successful main SHA.
2. Build backend and frontend production images.
3. Push SHA and `main` tags to private GHCR packages.
4. Connect to MateServer over SSH.
5. Stage the production Compose and operational scripts.
6. Authenticate to GHCR using the workflow's short-lived token.
7. Pin `/opt/MateERP/.env` to the exact SHA image tags.
8. Pull images.
9. Start and health-check PostgreSQL.
10. Run Django migrations.
11. Run `collectstatic`.
12. Run the idempotent document-metadata backfill.
13. Start/update backend and frontend containers.
14. Verify the backend and frontend localhost endpoints.
15. Log MateServer out of GHCR.

Required repository Actions secrets:

- `VPS_HOST`
- `VPS_USER`
- `VPS_SSH_KEY`
- `VPS_PORT` only when SSH is not on port 22

No application/database secret is stored in GitHub. Production application secrets live only in `/opt/MateERP/.env` on MateServer.

## Production environment

Create `/opt/MateERP/.env` from `deploy/.env.example`, then replace every secret placeholder before starting containers.

Required settings include:

- `MATEERP_BACKEND_IMAGE`
- `MATEERP_FRONTEND_IMAGE`
- `MATEERP_BACKEND_PORT=8035`
- `MATEERP_FRONTEND_PORT=3035`
- `MATEERP_BACKEND_URL=http://backend:8000`
- `DJANGO_DEBUG=false`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS=erp.netamate.com`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://erp.netamate.com`
- `DJANGO_SECURE_SSL_REDIRECT`
- `DJANGO_SECURE_HSTS_SECONDS`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`

The `.env` file must be mode `600`.

### HTTPS hardening sequence

Do not enable HSTS before TLS is working.

Initial state:

```text
DJANGO_SECURE_SSL_REDIRECT=false
DJANGO_SECURE_HSTS_SECONDS=0
```

After the Nginx HTTPS virtual host, certificate, CSRF behavior, login, and API access are verified:

```text
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SECURE_HSTS_SECONDS=<deliberate non-zero value>
```

Restart the backend after changing these values, then verify HTTP redirects, HTTPS application behavior, secure cookies, and CSRF-protected requests again.

## Persistent storage

PostgreSQL uses the named Docker volume `mateerp_pgdata`.

Finance documents use `/opt/MateERP/data/media`, bind-mounted to `/app/media` inside the backend container. Django collected static files use `/opt/MateERP/data/static`, bind-mounted to `/app/staticfiles`.

Finance documents are private business data. Nginx intentionally does not expose `/media/` as a public directory.

After deployment run:

```bash
# Inside the backend container, invoked through Docker Compose on MateServer.
python manage.py backfill_document_metadata
```

The command is idempotent.

## Initial instance bootstrap

Use the existing `bootstrap_instance` management command only when the production database has no MateERP organization.

The bootstrap password must be supplied through `MATEERP_BOOTSTRAP_PASSWORD`; never place the password in a command argument or repository file.

Example shape:

```bash
# MateServer SSH, with MATEERP_BOOTSTRAP_PASSWORD already supplied securely in the process environment.
docker compose exec -T backend python manage.py bootstrap_instance \
  --email '<initial-owner-email>' \
  --organization '<organization-name>' \
  --legal-entity '<legal-entity-name>' \
  --display-name '<full-name>' \
  --timezone '<timezone>' \
  --base-currency '<currency>' \
  --django-superuser
```

`--django-superuser` makes the same owner account usable for Django admin by setting `is_staff` and `is_superuser`.

## Nginx

MateServer uses host-native Nginx. The repository template is `deploy/nginx/mateerp.conf`.

Routing:

- `/api/` -> `127.0.0.1:8035`
- `/django-admin/` -> `127.0.0.1:8035`
- `/static/` -> `/opt/MateERP/data/static/`
- `/media/` -> denied/not publicly served
- all remaining paths -> `127.0.0.1:3035`

The configured request-body limit is `30M`, which safely allows the application's 25 MB finance-document limit with HTTP multipart overhead.

Always run:

```bash
# MateServer SSH
sudo nginx -t
```

Only reload Nginx after the configuration test succeeds.

## TLS

Use Certbot with host-native Nginx for `erp.netamate.com`.

Do not delete or replace certificates belonging to other NetaMate services.

After issuance verify:

- certificate chain and hostname
- Certbot renewal configuration
- HTTPS frontend
- HTTPS API health endpoint
- HTTP to HTTPS redirect
- secure session and CSRF cookies
- login/logout and CSRF-protected requests

## Notification scheduler

Phase 8 added:

```bash
python manage.py refresh_notifications --horizon-days 30
```

Production uses:

- `/etc/systemd/system/mateerp-notifications.service`
- `/etc/systemd/system/mateerp-notifications.timer`

The timer runs daily with a small randomized delay and is persistent across downtime.

Useful checks:

```bash
# MateServer SSH
sudo systemctl status mateerp-notifications.timer
sudo systemctl list-timers mateerp-notifications.timer
sudo journalctl -u mateerp-notifications.service
```

## PostgreSQL backup

The production backup script is `/opt/MateERP/scripts/backup-db.sh`.

It creates a PostgreSQL custom-format dump under:

`/opt/MateERP/backups/db/`

Each dump has a matching SHA-256 checksum file. Backup files are mode `600`. The automated retention policy is 14 days.

Production uses:

- `/etc/systemd/system/mateerp-backup.service`
- `/etc/systemd/system/mateerp-backup.timer`

Useful checks:

```bash
# MateServer SSH
sudo systemctl status mateerp-backup.timer
sudo systemctl list-timers mateerp-backup.timer
sudo journalctl -u mateerp-backup.service
```

## Restore validation

Do not test restoration against the production database.

Use the isolated validator:

```bash
# MateServer SSH
sudo /opt/MateERP/scripts/validate-restore.sh /opt/MateERP/backups/db/<backup>.dump
```

It starts a temporary PostgreSQL 17 container with no published host port, verifies the checksum when present, restores the dump, checks the restored Django migration table, and removes the temporary validation container.

A real backup and successful isolated restore validation are required before Phase 9 can be declared complete.

## Rollback

Application images are immutable by commit SHA. To roll back, use the `Deploy Production` workflow's manual dispatch and provide a previously deployed known-good SHA.

The workflow will pin both backend and frontend image variables to that SHA, pull them from private GHCR, and redeploy them.

Database migrations are handled separately. Never automatically reverse a migration merely because application images are rolled back.

### Failure handling

If a new container fails health checks:

1. Inspect `docker compose ps` and container logs.
2. Do not remove volumes.
3. Redeploy the previous known-good SHA.

If a migration fails:

1. Stop the deployment before replacing the running application where possible.
2. Inspect the migration error and database state.
3. Do not run destructive SQL or fake/reverse migrations without review.
4. Restore from a validated backup only when recovery truly requires it.

If frontend deployment fails:

1. Keep the backend/database intact.
2. Inspect frontend logs and local `3035` health.
3. Redeploy a known-good SHA.

If Nginx configuration fails:

1. Do not reload Nginx.
2. Fix the new MateERP site only.
3. Re-run `sudo nginx -t`.

If TLS issuance fails:

1. Keep the HTTP configuration intact.
2. Verify DNS and port 80 reachability.
3. Retry Certbot without altering unrelated certificates.

If the production database must be restored:

1. Treat it as a destructive recovery operation.
2. Take a fresh emergency backup when possible.
3. Stop application writes.
4. Restore only from a verified backup according to the incident plan.
5. Re-run migrations and full smoke validation.

## Production validation checklist

Before declaring go-live complete verify:

- backend health endpoint
- frontend accessibility
- valid HTTPS
- login and logout
- session persistence
- CSRF-protected actions
- organization and legal-entity switching
- Chart of Accounts
- journals
- expenses
- income
- financial accounts
- reconciliation
- subscriptions/domains/infrastructure
- budgets
- enterprise reporting
- audit log
- notifications
- finance document upload
- document SHA-256 metadata
- PostgreSQL persistence
- media persistence across container recreation
- notification refresh command
- scheduled notification timer
- database backup
- isolated restore validation
- backup timer
- container restart behavior
- localhost-only application bindings
- no PostgreSQL host/public binding
- Nginx routing
- rollback procedure

Phase 9 is complete only after this checklist passes on the real production domain.
