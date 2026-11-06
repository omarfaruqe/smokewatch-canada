-- One row per station per UTC hour. UTC_DATE has no zone suffix: it is UTC by definition.
with src as (
    select
        properties as p,
        geom,
        loaded_at,
        row_number() over (
            partition by properties ->> 'CLIMATE_IDENTIFIER', properties ->> 'UTC_DATE'
            order by loaded_at desc
        ) as rn
    from {{ source('raw', 'eccc_climate_hourly') }}
)

select
    p ->> 'CLIMATE_IDENTIFIER'                 as climate_id,
    p ->> 'STATION_NAME'                       as station_name,
    p ->> 'PROVINCE_CODE'                      as province_code,
    ((p ->> 'UTC_DATE')::timestamp at time zone 'UTC') as observed_at,
    (p ->> 'TEMP')::numeric                    as temp_c,
    (p ->> 'DEW_POINT_TEMP')::numeric          as dew_point_c,
    (p ->> 'RELATIVE_HUMIDITY')::numeric       as rh_pct,
    (p ->> 'WIND_SPEED')::numeric              as wind_speed_kmh,
    (p ->> 'WIND_DIRECTION')::numeric * 10     as wind_dir_deg,
    (p ->> 'STATION_PRESSURE')::numeric        as pressure_kpa,
    (p ->> 'VISIBILITY')::numeric              as visibility_km,
    (p ->> 'PRECIP_AMOUNT')::numeric           as precip_mm,
    nullif(p ->> 'WEATHER_ENG_DESC', 'NA')     as weather_desc_en,
    coalesce(p ->> 'WEATHER_ENG_DESC', '') ilike '%smoke%' as smoke_reported,
    p ->> 'TEMP_FLAG'                          as temp_flag,
    geom,
    loaded_at
from src
where rn = 1
