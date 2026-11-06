#!/usr/bin/env bash
# Export the dbt `marts` schema from the local warehouse to deploy/snapshot/marts.dump.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p deploy/snapshot
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-smokewatch}" -d "${POSTGRES_DB:-smokewatch}" \
  --schema=marts --format=custom --compress=6 --no-owner --no-privileges \
  > deploy/snapshot/marts.dump
ls -lh deploy/snapshot/marts.dump
