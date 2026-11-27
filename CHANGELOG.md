# Changelog

## Unreleased

### Added
- **AQHI forecast accuracy:** `fct_aqhi_forecast_pairs` and `fct_aqhi_forecast_skill` (MAE,
  bias, share within 1 point, probability of detection and false alarm ratio by lead time),
  served at `GET /aqhi/forecast-skill`.
- Architecture decision records (`docs/decisions.md`).
- Dependabot for GitHub Actions and Python dependencies (weekly, grouped).

### Fixed
- Numeric API values are returned as JSON numbers instead of strings.

## 0.2.0 — 2026-11-16

### Added
- **Nearest-station exposure estimate** from ~57,000 2021 dissemination areas (StatCan
  Geographic Attribute File), each assigned to its nearest AQHI location within 50 km, shown
  next to the whole-division count in the marts, API and dashboard.
- **Pipeline health:** `fct_pipeline_health` mart (load history and latest observation per
  dataset), `GET /health/pipeline`, and a "data through" line on the dashboard (EN/FR).
- **CI data tests:** a raw-layer fixture is loaded into PostGIS and a full `dbt build` runs on
  every push, followed by hand-computed expected results.
- **dbt docs and lineage** published to GitHub Pages from CI.
- **Low-impact snapshot deployment:** API image built off-server (`scripts/ship_image.sh`),
  CPU and memory caps, export and restore scripts, Caddy snippet.
- `scripts/dagster_dev.sh` with `config/dagster.yaml`: one Dagster run at a time, telemetry off.
- Short `Cache-Control` on data responses (`API_CACHE_SECONDS`, default 300); `/health` is
  never cached.

### Changed
- Hotspot, weather and daily-exposure models are **incremental** (ordinary builds about
  6.6 min instead of 14.7 min on the full 2023 season).
- Indexes are declared with dbt's `indexes` config instead of fixed-name hooks, so rebuilt
  tables always get them.
- The census-division figure is labelled a **whole-division count**, not an upper bound: the
  nearest-station estimate can exceed it when areas sit near a station across a border.

### Fixed
- Geographic Attribute File URL; StatCan downloads now reject HTML pages served in place of zips.
- dbt builds hanging on a background state-tracking feature (`track_commit_timestamp` off).

## 0.1.0 — 2026-11-06

First complete pipeline: CWFIS hotspots and fire perimeters, ECCC AQHI and weather, NAPS
archive with computed AQHI, StatCan 2021 census boundaries and population; S3 bronze layer,
incremental loads into PostGIS, dbt staging and marts (including SCD2 fire history and daily
population exposure), Dagster schedules and freshness checks, FastAPI and a bilingual map
dashboard, CI, and a 2023 season backfill validated against known events.
