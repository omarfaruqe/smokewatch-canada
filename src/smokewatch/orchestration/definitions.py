"""Dagster definitions: the whole SmokeWatch pipeline as software-defined assets.

    bronze_*   extract a source into S3 bronze (retried with exponential backoff)
    raw/*      load changed bronze partitions into Postgres `raw` (one asset per table)
    dbt models staging + marts, built by dbt; dbt tests appear as asset checks

Schedules (America/Toronto):
    hourly_air_quality   :20 past every hour - AQHI observations/forecasts -> downstream models
    daily_pipeline       07:35 - hotspots, perimeters, weather, AQHI re-pull -> all models

Note: no `from __future__ import annotations` here. Dagster inspects the real type of the
`context` annotation, and postponed (string) annotations make that check fail.
"""

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetExecutionContext,
    AssetKey,
    AssetSelection,
    AssetSpec,
    Backoff,
    DefaultScheduleStatus,
    Definitions,
    MaterializeResult,
    RetryPolicy,
    ScheduleDefinition,
    asset,
    asset_check,
    define_asset_job,
    multi_asset,
)
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets
from sqlalchemy import text

from smokewatch.db import get_engine  # importing config also loads .env for dbt subprocesses
from smokewatch.extractors import (
    cwfis_hotspots,
    cwfis_perimeters,
    eccc_aqhi,
    eccc_climate,
    statcan,
)
from smokewatch.loaders import bronze_features, statcan_census
from smokewatch.storage import get_store

REPO_ROOT = Path(__file__).resolve().parents[3]
dbt_project = DbtProject(project_dir=REPO_ROOT / "transform", profiles_dir=REPO_ROOT / "transform")
dbt_project.prepare_if_dev()

RETRY = RetryPolicy(max_retries=3, delay=30, backoff=Backoff.EXPONENTIAL)


def _store():
    return get_store("s3")


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


# --- bronze: extraction -------------------------------------------------------------------

@asset(group_name="bronze", retry_policy=RETRY, kinds={"python", "s3"})
def bronze_hotspots() -> MaterializeResult:
    """CWFIS satellite hotspots, rolling last 24 h."""
    r = cwfis_hotspots.extract(_store())
    return MaterializeResult(metadata={"features": r.feature_count, "key": r.data_key})


@asset(group_name="bronze", retry_policy=RETRY, kinds={"python", "s3"})
def bronze_fire_perimeters() -> MaterializeResult:
    """CWFIS current fire perimeters, one snapshot per UTC day."""
    r = cwfis_perimeters.snapshot(_store())
    return MaterializeResult(metadata={"features": r.feature_count, "key": r.data_key})


@asset(group_name="bronze", retry_policy=RETRY, kinds={"python", "s3"})
def bronze_aqhi_observations() -> MaterializeResult:
    """ECCC hourly AQHI for today, plus yesterday to pick up late amendments."""
    store, today = _store(), _utc_today()
    rs = [eccc_aqhi.observations(store, today - timedelta(days=1)),
          eccc_aqhi.observations(store, today)]
    return MaterializeResult(metadata={"features": sum(r.feature_count for r in rs)})


@asset(group_name="bronze", retry_policy=RETRY, kinds={"python", "s3"})
def bronze_aqhi_forecasts() -> MaterializeResult:
    """ECCC AQHI forecast window, merged into per-publication-date partitions."""
    rs = eccc_aqhi.forecasts(_store())
    return MaterializeResult(metadata={"partitions": len(rs),
                                       "features": sum(r.feature_count for r in rs)})


@asset(group_name="bronze", retry_policy=RETRY, kinds={"python", "s3"})
def bronze_weather() -> MaterializeResult:
    """ECCC hourly climate for the two previous UTC days (the archive is published late)."""
    store, today = _store(), _utc_today()
    rs = [eccc_climate.hourly(store, today - timedelta(days=d)) for d in (2, 1)]
    return MaterializeResult(metadata={"features": sum(r.feature_count for r in rs)})


@asset(group_name="bronze", retry_policy=RETRY, kinds={"python", "s3"})
def bronze_statcan() -> MaterializeResult:
    """StatCan 2021 Census boundaries and population (static; downloaded once)."""
    rs = statcan.fetch(_store())
    return MaterializeResult(metadata={"downloaded": sum(not r.skipped for r in rs)})


# --- raw: load into Postgres --------------------------------------------------------------

# raw table -> (loader dataset, upstream bronze asset)
RAW_FEATURES = {
    "cwfis_hotspots": ("hotspots", bronze_hotspots),
    "cwfis_fire_perimeters": ("fire_perimeters", bronze_fire_perimeters),
    "eccc_aqhi_observations": ("aqhi_observations", bronze_aqhi_observations),
    "eccc_aqhi_forecasts": ("aqhi_forecasts", bronze_aqhi_forecasts),
    "eccc_climate_hourly": ("weather", bronze_weather),
}

# dataset -> freshest acceptable partition date, as days before today (UTC)
MAX_PARTITION_AGE_DAYS = {
    "hotspots": 1, "fire_perimeters": 1, "aqhi_observations": 0,
    "aqhi_forecasts": 1, "weather": 3,
}


@multi_asset(
    specs=[
        AssetSpec(["raw", table], deps=[upstream], group_name="raw", kinds={"postgres"})
        for table, (_, upstream) in RAW_FEATURES.items()
    ],
    can_subset=True,
    retry_policy=RETRY,
)
def raw_features(context: AssetExecutionContext):
    """Load changed bronze partitions into raw tables (skips partitions with unchanged sha256)."""
    store, engine = _store(), get_engine()
    for key in context.selected_asset_keys:
        dataset = RAW_FEATURES[key.path[-1]][0]
        stats = bronze_features.load_dataset(store, dataset, engine)
        yield MaterializeResult(asset_key=key, metadata=stats)


@multi_asset(
    specs=[
        AssetSpec(["raw", t], deps=[bronze_statcan], group_name="raw", kinds={"postgres"})
        for t in ("statcan_census_divisions", "statcan_provinces", "statcan_population_cd")
    ],
)
def raw_census():
    """Load census boundaries and population into raw (tables replaced on each run)."""
    counts = statcan_census.load(_store())
    names = {"census_divisions": "statcan_census_divisions", "provinces": "statcan_provinces",
             "population_cd": "statcan_population_cd"}
    for name, table in names.items():
        yield MaterializeResult(asset_key=AssetKey(["raw", table]), metadata={"rows": counts[name]})


def _freshness_check(table: str, dataset: str, max_age: int):
    @asset_check(asset=AssetKey(["raw", table]), name="partition_freshness",
                 description=f"Newest loaded partition is at most {max_age} day(s) old (UTC).")
    def _check() -> AssetCheckResult:
        with get_engine().connect() as conn:
            parts = conn.execute(
                text("SELECT partition FROM raw._load_log WHERE dataset = :d"), {"d": dataset}
            ).scalars().all()
        dates = [date.fromisoformat(m.group(1)) for p in parts
                 if (m := re.search(r"(?:date|pub_date)=(\d{4}-\d{2}-\d{2})", p))]
        newest = max(dates) if dates else None
        age = (_utc_today() - newest).days if newest else None
        return AssetCheckResult(
            passed=age is not None and age <= max_age,
            severity=AssetCheckSeverity.WARN,
            metadata={"newest_partition": str(newest), "age_days": age, "max_age_days": max_age},
        )
    return _check


freshness_checks = [
    _freshness_check(table, dataset, MAX_PARTITION_AGE_DAYS[dataset])
    for table, (dataset, _) in RAW_FEATURES.items()
]


# --- dbt: staging + marts -----------------------------------------------------------------

@dbt_assets(manifest=dbt_project.manifest_path)
def smokewatch_dbt(context: AssetExecutionContext, dbt: DbtCliResource):
    """All dbt models; their dbt tests run with them and report as asset checks."""
    yield from dbt.cli(["build"], context=context).stream()


# --- jobs and schedules -------------------------------------------------------------------

hourly_air_quality_job = define_asset_job(
    "hourly_air_quality",
    selection=AssetSelection.assets(bronze_aqhi_observations, bronze_aqhi_forecasts).downstream(),
)

daily_pipeline_job = define_asset_job(
    "daily_pipeline",
    selection=(AssetSelection.groups("bronze") - AssetSelection.assets(bronze_statcan)).downstream(),
)

defs = Definitions(
    assets=[bronze_hotspots, bronze_fire_perimeters, bronze_aqhi_observations,
            bronze_aqhi_forecasts, bronze_weather, bronze_statcan,
            raw_features, raw_census, smokewatch_dbt],
    asset_checks=freshness_checks,
    jobs=[hourly_air_quality_job, daily_pipeline_job],
    schedules=[
        ScheduleDefinition(job=hourly_air_quality_job, cron_schedule="20 * * * *",
                           execution_timezone="America/Toronto",
                           default_status=DefaultScheduleStatus.RUNNING),
        ScheduleDefinition(job=daily_pipeline_job, cron_schedule="35 7 * * *",
                           execution_timezone="America/Toronto",
                           default_status=DefaultScheduleStatus.RUNNING),
    ],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
)
