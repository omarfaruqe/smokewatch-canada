#!/usr/bin/env bash
# Restore deploy/snapshot/marts.dump into the server database (replaces the marts schema).
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source deploy/.env; set +a
DC="docker compose -f deploy/docker-compose.yml --env-file deploy/.env"
$DC exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 \
  -c "CREATE EXTENSION IF NOT EXISTS postgis; DROP SCHEMA IF EXISTS marts CASCADE;"
# One job (no parallel restore): the database container is CPU-capped and the host is shared.
$DC exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges \
  --jobs=1 --exit-on-error /snapshot/marts.dump
$DC exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "ANALYZE;" \
  -c "SELECT count(*) AS hotspots FROM marts.fct_hotspots;"
