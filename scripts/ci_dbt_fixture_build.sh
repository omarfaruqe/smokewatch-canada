#!/usr/bin/env bash
# Load the raw-layer fixture into an empty database, run a full dbt build (models + tests),
# then check hand-computed expected results (transform/ci/expectations.sql).
# CI runs this against a PostGIS service container. Locally, point it at a scratch database:
#   POSTGRES_DB=smokewatch_ci scripts/ci_dbt_fixture_build.sh --docker
set -euo pipefail
cd "$(dirname "$0")/.."
FIXTURE=transform/ci/fixtures.sql
if [[ "${1:-}" == "--docker" ]]; then
    # Local: use psql inside the compose Postgres container; create the scratch DB if needed.
    docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres -tc \
        "SELECT 1 FROM pg_database WHERE datname = '$POSTGRES_DB'" | grep -q 1 \
      || docker compose exec -T postgres createdb -U "$POSTGRES_USER" "$POSTGRES_DB"
    docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
        -v ON_ERROR_STOP=1 -q < "$FIXTURE"
else
    PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" \
        -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -q -f "$FIXTURE"
fi
dbt build --project-dir transform --profiles-dir transform --full-refresh

EXPECT=transform/ci/expectations.sql
if [[ "${1:-}" == "--docker" ]]; then
    docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
        -v ON_ERROR_STOP=1 -q < "$EXPECT"
else
    PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" \
        -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -q -f "$EXPECT"
fi
