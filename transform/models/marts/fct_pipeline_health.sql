-- One row per dataset: what has been loaded (from raw._load_log) and how recent the modelled
-- data is. Lives in marts so the deployed snapshot carries its own freshness information.
--   last_loaded_at   when the loader last wrote a partition of this dataset
--   newest_partition the most recent bronze partition date (date=, pub_date= or year=)
--   data_through     the latest observation in the marts built from it
with datasets(dataset, description) as (
    values
        ('hotspots',          'CWFIS satellite hotspots'),
        ('fire_perimeters',   'CWFIS daily fire perimeter snapshots'),
        ('season_perimeters', 'CWFIS archived season perimeters'),
        ('aqhi_observations', 'ECCC hourly AQHI observations'),
        ('aqhi_forecasts',    'ECCC AQHI forecasts'),
        ('weather',           'ECCC hourly climate observations'),
        ('naps_hourly',       'NAPS hourly PM2.5, O3, NO2 (computed AQHI)')
),

loads as (
    select
        dataset,
        count(*)                               as partitions_loaded,
        sum(row_count)::bigint                 as rows_loaded,
        max(loaded_at)                         as last_loaded_at,
        max(to_date(substring(partition from '(?:date|pub_date)=(\d{4}-\d{2}-\d{2})'),
                    'YYYY-MM-DD'))             as newest_partition_date,
        max(substring(partition from 'year=(\d{4})')::integer) as newest_partition_year
    from {{ source('raw', '_load_log') }}
    group by dataset
),

data_through as (
    select 'hotspots' as dataset, max(detected_at) as data_through
    from {{ ref('fct_hotspots') }}
    union all
    select 'fire_perimeters', max(valid_from)::timestamp at time zone 'UTC'
    from {{ ref('dim_fire_perimeter_history') }}
    union all
    select 'season_perimeters', max(last_detected_at)
    from {{ ref('fct_fire_season_perimeters') }}
    union all
    select 'aqhi_observations', max(observed_at)
    from {{ ref('fct_aqhi_hourly') }} where aqhi_source = 'eccc_observed'
    union all
    select 'aqhi_forecasts', max(valid_at)
    from {{ ref('stg_eccc__aqhi_forecasts_hourly') }}
    union all
    select 'weather', max(observed_at)
    from {{ ref('stg_eccc__weather_hourly') }}
    union all
    select 'naps_hourly', max(observed_at)
    from {{ ref('fct_aqhi_hourly') }} where aqhi_source = 'naps_computed'
)

select
    d.dataset,
    d.description,
    coalesce(l.partitions_loaded, 0)           as partitions_loaded,
    coalesce(l.rows_loaded, 0)                 as rows_loaded,
    l.last_loaded_at,
    l.newest_partition_date,
    l.newest_partition_year,
    t.data_through,
    now()                                      as built_at
from datasets d
left join loads l using (dataset)
left join data_through t using (dataset)
