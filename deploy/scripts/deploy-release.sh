#!/usr/bin/env bash
# Deploy an exact MateERP release image pair and fail unless the running services match it.
set -euo pipefail

: "${DEPLOY_SHA:?DEPLOY_SHA is required}"
: "${RUN_MIGRATIONS:?RUN_MIGRATIONS is required}"

if [[ ! "${DEPLOY_SHA}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "DEPLOY_SHA must be an exact 40-character lowercase Git SHA." >&2
  exit 1
fi
if [[ "${RUN_MIGRATIONS}" != "true" && "${RUN_MIGRATIONS}" != "false" ]]; then
  echo "RUN_MIGRATIONS must be true or false." >&2
  exit 1
fi

cd /opt/MateERP
test -f .env

backend_image="ghcr.io/netamate/mateerp-backend:${DEPLOY_SHA}"
frontend_image="ghcr.io/netamate/mateerp-frontend:${DEPLOY_SHA}"

sed -i -E "s|^MATEERP_BACKEND_IMAGE=.*|MATEERP_BACKEND_IMAGE=${backend_image}|" .env
sed -i -E "s|^MATEERP_FRONTEND_IMAGE=.*|MATEERP_FRONTEND_IMAGE=${frontend_image}|" .env
chmod 600 .env

docker compose pull
docker compose up -d database

for _ in $(seq 1 30); do
  state="$(docker inspect -f '{{.State.Health.Status}}' mateerp-database-1 2>/dev/null || true)"
  [[ "${state}" == "healthy" ]] && break
  sleep 2
done
[[ "$(docker inspect -f '{{.State.Health.Status}}' mateerp-database-1)" == "healthy" ]]

if [[ "${RUN_MIGRATIONS}" == "true" ]]; then
  backup_output="$(/opt/MateERP/scripts/backup-db.sh)"
  printf '%s\n' "${backup_output}"
  backup_path="$(printf '%s\n' "${backup_output}" | sed -n 's/^MateERP database backup created: //p' | tail -n 1)"
  test -n "${backup_path}"
  /opt/MateERP/scripts/validate-restore.sh "${backup_path}"
  docker compose run --rm -T backend python manage.py migrate --noinput </dev/null
  docker compose run --rm -T backend python manage.py backfill_document_metadata </dev/null
fi

docker compose run --rm -T backend python manage.py collectstatic --noinput </dev/null
docker compose up -d --force-recreate backend frontend

for service in backend frontend; do
  cid="$(docker compose ps -q "${service}")"
  test -n "${cid}"
  for _ in $(seq 1 30); do
    state="$(docker inspect -f '{{.State.Health.Status}}' "${cid}" 2>/dev/null || true)"
    [[ "${state}" == "healthy" ]] && break
    sleep 2
  done
  [[ "$(docker inspect -f '{{.State.Health.Status}}' "${cid}")" == "healthy" ]]
done

backend_cid="$(docker compose ps -q backend)"
frontend_cid="$(docker compose ps -q frontend)"
[[ "$(docker inspect -f '{{.Config.Image}}' "${backend_cid}")" == "${backend_image}" ]]
[[ "$(docker inspect -f '{{.Config.Image}}' "${frontend_cid}")" == "${frontend_image}" ]]

docker compose ps
curl --fail --silent --show-error http://127.0.0.1:8035/api/v1/health/ >/dev/null
curl --fail --silent --show-error http://127.0.0.1:3035/ >/dev/null
curl --fail --silent --show-error http://127.0.0.1:3035/images/logo.png >/dev/null
curl --fail --silent --show-error http://127.0.0.1:3035/images/favicon.png >/dev/null

printf 'MateERP release %s deployed and verified.\n' "${DEPLOY_SHA}"
