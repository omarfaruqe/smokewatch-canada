# SmokeWatch Canada

A national data engineering platform that tracks wildfires, smoke and air quality across all
Canadian provinces and territories, and estimates daily population exposure to poor air.

*Version française à venir.*

## Data sources

| Source | Publisher | Content | Cadence |
|---|---|---|---|
| CWFIS hotspots (WFS) | Natural Resources Canada | Satellite-detected fire hotspots | Daily |
| CWFIS fire perimeters | Natural Resources Canada | Current fire perimeters, snapshotted daily for SCD2 history | Daily |
| MSC GeoMet / Datamart | Environment and Climate Change Canada | AQHI observations and forecasts, weather | Hourly |
| Census 2021 | Statistics Canada | Census division and province boundaries, population (table 98-10-0007-01) | Static |

## Architecture (target)

```
extractors (Python) ──► S3 bronze (SeaweedFS) (raw, partitioned by source/date)
                              │
                              ▼
                    Postgres + PostGIS ──► dbt silver / gold ──► FastAPI + map dashboard
                              ▲
              orchestration (Dagster) · data quality (dbt tests / Soda)
```

## Quick start

```bash
cp .env.example .env            # then edit the passwords
docker compose up -d            # Postgres+PostGIS on :5433, SeaweedFS S3 on :8333 (filer UI :8888)
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                       # offline tests
smokewatch hotspots --sink s3   # last 24 h of hotspots -> bronze
smokewatch hotspots --start 2023-06-01 --end 2023-06-07 --sink s3   # backfill
smokewatch aqhi observations --sink s3   # today's hourly AQHI
smokewatch aqhi forecasts --sink s3      # merge current forecast window
smokewatch weather --sink s3             # yesterday's hourly weather, all stations
smokewatch statcan --sink s3             # 2021 Census boundaries + population (once)
smokewatch perimeters --sink s3          # daily fire perimeter snapshot
smokewatch load census                   # bronze -> PostGIS raw schema (once)
smokewatch load features                 # bronze -> raw, only changed partitions
set -a && source .env && set +a && dbt build --project-dir transform --profiles-dir transform
```

## Roadmap

- [x] Sprint 1 — Repo setup, local stack, CWFIS hotspot extractor to bronze
- [x] Sprint 2 — AQHI and weather ingestion
- [x] Sprint 3 — Census boundaries and population in PostGIS
- [x] Sprint 4 — dbt models, spatial joins, SCD2 fire tracking
- [ ] Sprint 5 — Orchestration and data quality
- [ ] Sprint 6 — Historical backfill (2023 season)
- [ ] Sprint 7 — API and map dashboard
- [ ] Sprint 8 — CI/CD, docs, bilingual README

## Licence and data attribution

Code: MIT. Data: contains information licensed under the
[Open Government Licence – Canada](https://open.canada.ca/en/open-government-licence-canada).
