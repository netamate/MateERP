#!/usr/bin/env bash
# Validate a MateERP backup by restoring it into an isolated disposable PostgreSQL container.
set -euo pipefail

backup_path="${1:?Usage: validate-restore.sh /path/to/mateerp-backup.dump}"
if [[ ! -f "${backup_path}" ]]; then
  echo "Backup file not found: ${backup_path}" >&2
  exit 1
fi

if [[ -f "${backup_path}.sha256" ]]; then
  sha256sum --check "${backup_path}.sha256"
fi

container_name="mateerp-restore-check-$$"
restore_password="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"

cleanup() {
  docker rm -f "${container_name}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker run -d --rm \
  --name "${container_name}" \
  -e POSTGRES_PASSWORD="${restore_password}" \
  -e POSTGRES_DB=restorecheck \
  -v "${backup_path}:/backup.dump:ro" \
  postgres:17-alpine >/dev/null

# The official PostgreSQL image briefly starts a temporary server while
# initializing a fresh data directory, then shuts it down and starts the final
# server. pg_isready can succeed during that temporary window, so wait until
# the entrypoint reports that initialization is complete before accepting
# readiness from the final server.
init_complete=false
for _ in $(seq 1 60); do
  if docker logs "${container_name}" 2>&1 | grep -Fq     "PostgreSQL init process complete; ready for start up."; then
    init_complete=true
    break
  fi
  sleep 1
done
if [[ "${init_complete}" != "true" ]]; then
  echo "Timed out waiting for PostgreSQL restore-check initialization." >&2
  docker logs "${container_name}" >&2 || true
  exit 1
fi

ready=false
for _ in $(seq 1 30); do
  if docker exec "${container_name}"     pg_isready -U postgres -d restorecheck >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "${ready}" != "true" ]]; then
  echo "Timed out waiting for final PostgreSQL restore-check server." >&2
  docker logs "${container_name}" >&2 || true
  exit 1
fi
docker exec "${container_name}" pg_restore \
  -U postgres \
  -d restorecheck \
  --no-owner \
  --no-privileges \
  /backup.dump

docker exec "${container_name}" psql \
  -U postgres \
  -d restorecheck \
  -v ON_ERROR_STOP=1 \
  -Atqc "SELECT count(*) FROM django_migrations;" >/dev/null

printf 'MateERP restore validation passed for %s\n' "${backup_path}"
