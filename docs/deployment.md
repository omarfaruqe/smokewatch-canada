# Deployment (snapshot mode)

The full pipeline (extraction, bronze, Dagster, dbt) runs on the development machine. The
server runs only what the public needs: Postgres + PostGIS holding the dbt `marts` schema, and
the API with the dashboard, published by the existing gateway Caddy at `/smokewatch/`.

```
Mac: pipeline -> marts --pg_dump--> marts.dump --scp--> server: Postgres <- API <- Caddy /smokewatch/
```

Both containers bind to `127.0.0.1` only (API 8095, DB 5434 by default; see `deploy/.env`),
and the compose project is named `smokewatch`, so existing apps on the server are untouched.

## Sharing the server with other workloads

The server also runs long scientific jobs, so the deployment is designed not to compete:

- The API image is built on the development machine (`scripts/ship_image.sh`, linux/amd64)
  and loaded on the server; the server never builds it.
- Containers are capped: Postgres 1 CPU / 1 GB, API 0.5 CPU / 512 MB (see `deploy/.env`),
  one uvicorn worker, no parallel query or parallel restore workers.
- Check free memory before deploying: if the host runs out of RAM, the kernel's OOM killer
  tends to pick the largest process, which may be the scientific job.

## First deployment

On the Mac:

```bash
scripts/export_snapshot.sh                                  # -> deploy/snapshot/marts.dump
scripts/ship_image.sh                                       # -> deploy/snapshot/smokewatch-api.tar.gz
scp deploy/snapshot/marts.dump deploy/snapshot/smokewatch-api.tar.gz \
    <user>@<server>:~/smokewatch-canada/deploy/snapshot/
```

On the server:

```bash
git clone https://github.com/omarfaruqe/smokewatch-canada.git ~/smokewatch-canada
cd ~/smokewatch-canada && mkdir -p deploy/snapshot
cp deploy/.env.example deploy/.env                          # set POSTGRES_PASSWORD
gunzip -c deploy/snapshot/smokewatch-api.tar.gz | docker load
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --no-build
scripts/restore_snapshot.sh
```

Add `deploy/Caddyfile.snippet` to `~/gateway/Caddyfile` and reload the gateway Caddy.

## Refreshing the data

```bash
# Mac
scripts/export_snapshot.sh && scp deploy/snapshot/marts.dump <user>@<server>:~/smokewatch-canada/deploy/snapshot/
# Server
cd ~/smokewatch-canada && scripts/restore_snapshot.sh
```

## Updating the code

```bash
# Server
# Mac: scripts/ship_image.sh && scp deploy/snapshot/smokewatch-api.tar.gz <user>@<server>:~/smokewatch-canada/deploy/snapshot/
# Server:
cd ~/smokewatch-canada && git pull && gunzip -c deploy/snapshot/smokewatch-api.tar.gz | docker load \
  && docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --no-build
```

## Incremental models and backfills

`stg_cwfis__hotspots`, `fct_hotspots` and `stg_eccc__weather_hourly` process only raw rows
loaded since their last run; `fct_daily_exposure` recomputes the last
`exposure_lookback_days` days (default 3). After backfilling older dates, rebuild once with:

```bash
dbt build --project-dir transform --profiles-dir transform --full-refresh
```
