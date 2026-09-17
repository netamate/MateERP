#!/usr/bin/env bash
# Create a PostgreSQL-native custom-format backup without exposing database credentials on the host command line.
set -euo pipefail

cd /opt/MateERP
umask 077

backup_dir="/opt/MateERP/backups/db"
mkdir -p "${backup_dir}"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
final_path="${backup_dir}/mateerp-${timestamp}.dump"
tmp_path="${final_path}.tmp"

cleanup() {
  rm -f "${tmp_path}"
}
trap cleanup EXIT

docker compose exec -T database sh -ec \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "${tmp_path}"

test -s "${tmp_path}"
mv "${tmp_path}" "${final_path}"
sha256sum "${final_path}" > "${final_path}.sha256"
chmod 600 "${final_path}" "${final_path}.sha256"

# Keep 14 days of database dumps and matching checksum files.
find "${backup_dir}" -type f \( -name 'mateerp-*.dump' -o -name 'mateerp-*.dump.sha256' \) -mtime +14 -delete

printf 'MateERP database backup created: %s\n' "${final_path}"
