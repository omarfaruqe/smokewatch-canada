{{ config(
    materialized='incremental',
    unique_key='hotspot_id',
    incremental_strategy='delete+insert',
    on_schema_change='append_new_columns',
    post_hook=[
        "create index if not exists {{ this.name }}_id_idx on {{ this }} (hotspot_id)",
        "create index if not exists {{ this.name }}_geom_idx on {{ this }} using gist (geom)",
        "create index if not exists {{ this.name }}_geom3347_idx on {{ this }} using gist (geom_3347)",
    ]
) }}

-- Incremental: only raw rows loaded since the last run are processed (watermark on
-- loaded_at), and a hotspot seen again (24 h layer, then season layer) replaces its earlier
-- row. Rows deleted from raw are not removed here: use --full-refresh after rebuilding raw.
-- One row per hotspot. The same uid appears in the 24 h and season layers and in repeated
-- daily pulls, so keep the most recently loaded copy.
with src as (
    select
        (properties ->> 'uid')::bigint as uid,
        properties as p,
        geom,
        partition,
        loaded_at,
        row_number() over (
            partition by properties ->> 'uid' order by loaded_at desc, partition desc
        ) as rn
    from {{ source('raw', 'cwfis_hotspots') }}
    where properties ->> 'uid' is not null
    {% if is_incremental() %}
      and loaded_at > (select coalesce(max(loaded_at), '-infinity') from {{ this }})
    {% endif %}
)

select
    uid                                        as hotspot_id,
    (p ->> 'rep_date')::timestamptz            as detected_at,
    ((p ->> 'rep_date')::timestamptz at time zone 'UTC')::date as detected_date_utc,
    p ->> 'agency'                             as agency,
    p ->> 'source'                             as detection_source,
    p ->> 'sensor'                             as sensor,
    p ->> 'satellite'                          as satellite,
    (p ->> 'frp')::numeric                     as frp_mw,
    (p ->> 'estarea')::numeric                 as est_area_ha,
    (p ->> 'hfi')::numeric                     as head_fire_intensity,
    (p ->> 'ros')::numeric                     as rate_of_spread,
    (p ->> 'temp')::numeric                    as temp_c,
    (p ->> 'rh')::numeric                      as rh_pct,
    (p ->> 'ws')::numeric                      as wind_speed_kmh,
    (p ->> 'wd')::numeric                      as wind_dir_deg,
    (p ->> 'pcp')::numeric                     as precip_mm,
    (p ->> 'ffmc')::numeric                    as ffmc,
    (p ->> 'dmc')::numeric                     as dmc,
    (p ->> 'dc')::numeric                      as dc,
    (p ->> 'isi')::numeric                     as isi,
    (p ->> 'bui')::numeric                     as bui,
    (p ->> 'fwi')::numeric                     as fwi,
    p ->> 'fuel'                               as fuel_type,
    p ->> 'ecozone'                            as ecozone,
    (p ->> 'm3_confidence')::numeric           as confidence,
    geom,
    ST_Transform(geom, 3347)::geometry(Point, 3347) as geom_3347,
    partition                                  as bronze_partition,
    loaded_at
from src
where rn = 1
