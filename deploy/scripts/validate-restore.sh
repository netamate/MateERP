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

ready=false
for _ in $(seq 1 60); do
  # The official PostgreSQL image briefly starts a temporary server while it
  # initializes an empty data directory. pg_isready can succeed during that
  # phase, immediately before the entrypoint shuts the temporary server down.
  # Wait until PID 1 has exec'd the final postgres process and it accepts SQL.
  if docker exec "${container_name}" sh -ec '
    [ "$(cat /proc/1/comm)" = "postgres" ] &&
    pg_isready -U postgres -d restorecheck >/dev/null 2>&1 &&
    [ "$(psql -U postgres -d restorecheck -Atqc "SELECT 1")" = "1" ]
  '; then
    ready=true
    break
  fi
  sleep 1
done

if [[ "${ready}" != "true" ]]; then
  docker logs "${container_name}" >&2 || true
  echo "Disposable PostgreSQL restore target did not reach final readiness." >&2
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
