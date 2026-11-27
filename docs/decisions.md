# Architecture decisions

Short records of the choices that shaped SmokeWatch Canada: the context, the decision, and
what it costs. Newest last.

## 1. Partition everything by UTC day

**Context.** Sources span six time zones, and NAPS reports in local *standard* time all year.
**Decision.** Bronze partitions, loads and marts use UTC days; NAPS hours are converted with
each station's standard offset.
**Consequences.** One consistent calendar nationally. A late-evening Montreal snapshot can land
in the next day's partition, and "day" in the dashboard means a UTC day.

## 2. Idempotent bronze partitions with sha256 manifests

**Context.** Extractors are retried and re-run (late AQHI amendments, re-pulled weather).
**Decision.** Each run overwrites its partition and writes a manifest with a sha256; loaders
reload a partition only when its sha256 changes, deleting and inserting in one transaction.
**Consequences.** Re-runs never duplicate rows and cost nothing when data is unchanged. AQHI
forecasts are the exception: the API serves a rolling window, so they are merged by id into
publication-date partitions to keep rows that age out.

## 3. Raw layer as jsonb plus geometry

**Context.** Five sources with different, evolving schemas.
**Decision.** Every raw feature table stores `properties jsonb` and a PostGIS `geom`; typing
happens in dbt staging. NAPS and StatCan tables are the exception (text columns, bulk COPY).
**Consequences.** A new or renamed source field never breaks a load; the cost is larger raw
tables and casting in staging.

## 4. SeaweedFS instead of MinIO for S3 storage

**Context.** MinIO stopped publishing free Docker images in October 2025.
**Decision.** SeaweedFS (S3 API, pinned 4.50) for the local bronze layer; boto3 code unchanged.
**Consequences.** Any S3-compatible store (AWS S3, Azure via a gateway) can replace it by
changing settings only.

## 5. SCD Type 2 fire history derived in SQL, not with dbt snapshots

**Context.** CWFIS only exposes current perimeters; dbt snapshots record changes only when
they run.
**Decision.** Keep one bronze snapshot per day and derive versions in SQL (hash comparison,
`valid_from`/`valid_to`), rebuildable from bronze.
**Consequences.** History is deterministic and reproducible. It assumes CWFIS keeps feature
ids stable across days, which needs checking once enough snapshots exist.

## 6. Historical AQHI computed from NAPS measurements

**Context.** ECCC's realtime AQHI API covers only recent days; 2023 values are not served.
**Decision.** Compute AQHI from NAPS hourly PM2.5, O3 and NO2 with Health Canada's formula on
3-hour rolling means, choosing the instrument with the most valid hours per station.
**Consequences.** A full 2023 season record, validated against Montreal on 2023-06-25 (computed
15-17, reported "10+"). Computed values are labelled `naps_computed` everywhere.

## 7. Two exposure estimates, neither called a bound

**Context.** The first method counted a whole census division once any station in it was
high risk; this was described as an upper bound.
**Decision.** Add a nearest-station estimate from ~57,000 dissemination areas (nearest AQHI
location within 50 km) and keep the whole-division count beside it.
**Consequences.** The comparison showed the "upper bound" label was wrong: assignment across
division borders can make the nearest-station figure larger (2023-06-26: 6.6 M vs 5.4 M). About
22% of the population is beyond 50 km of any AQHI location and is reported as not covered.

## 8. Incremental models with a lookback window

**Context.** A full build over the 2023 season took about 15 minutes.
**Decision.** Hotspot, weather and exposure models are incremental (loaded_at watermark;
exposure recomputes the last 3 days). Backfills of older dates need one `--full-refresh`.
**Consequences.** Ordinary builds about 6.6 minutes; static census and NAPS models still
rebuild in full when run manually, but are outside the scheduled jobs' selection.

## 9. dbt Core 1.12 on Python 3.13

**Context.** dagster-dbt did not support Python 3.14; dbt v2 became the default for new
projects in 2026.
**Decision.** Pin Python below 3.14, dbt-core 1.12.6 with dbt-postgres 1.11.0, Dagster 1.13.29
with dagster-dbt 0.29.29.
**Consequences.** A mature, widely documented toolchain; moving to dbt v2 is a later project.

## 10. Leave track_commit_timestamp off

**Context.** Enabling it silenced warnings from a state-tracking feature in dbt 1.12, which then
became fully active; two builds hung before opening any database connection.
**Decision.** Keep the Postgres default (off); accept "continuing without state" log lines.
**Consequences.** No hangs since. Dagster also runs one job at a time (`config/dagster.yaml`).

## 11. Index declarations instead of hooks

**Context.** Post-hooks with fixed index names were skipped after table rebuilds, because the
renamed backup table still held the names.
**Decision.** Use dbt-postgres `indexes` configs, which generate unique names on each build.
**Consequences.** Rebuilt tables always have their spatial and key indexes.

## 12. Snapshot deployment on a shared server

**Context.** The host also runs long scientific jobs; the full warehouse is ~10 GB.
**Decision.** Deploy only the marts schema (~150 MB dump) with the API; build the image
off-server; cap containers (Postgres 1 CPU / 1 GB, API 0.5 CPU / 512 MB); no parallel
query or restore workers.
**Consequences.** Negligible load on the host; data refreshes are a manual export and restore.
