# MateERP Production Deployment Assets

This directory contains the production deployment boundary for MateERP on MateServer.

## Files

- `docker-compose.yml`: production Compose stack using private GHCR images, PostgreSQL 17, localhost-only web bindings, health checks, persistent database/media/static storage, and an internal bridge network.
- `.env.example`: secret-free production environment template for `/opt/MateERP/.env`.
- `nginx/mateerp.conf`: HTTP-first host-native Nginx site for `erp.netamate.com`.
- `scripts/backup-db.sh`: PostgreSQL custom-format backups with SHA-256 checksums and 14-day retention.
- `scripts/validate-restore.sh`: isolated disposable PostgreSQL restore validation.
- `systemd/mateerp-notifications.*`: daily Phase 8 notification refresh.
- `systemd/mateerp-backup.*`: daily database backup schedule.

## Live port allocation

The production ports were chosen only after inspecting MateServer listeners:

- backend: `127.0.0.1:8035`
- frontend: `127.0.0.1:3035`
- database: Docker-internal only

Do not publish PostgreSQL or bind application services to `0.0.0.0`.

## Production directory

Runtime files live under `/opt/MateERP/`. Source code is not built on MateServer. GitHub Actions builds production images, pushes them to private GHCR packages, and MateServer pulls the exact commit-SHA image tags.

See `docs/phase-9-production-deployment.md` for the full deployment, TLS, backup, restore, scheduler, rollback, and production validation procedure.
