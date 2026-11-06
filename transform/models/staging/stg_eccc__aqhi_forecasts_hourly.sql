-- Hourly AQHI forecasts (aqhi_type = AQHI-Forecast), one row per forecast id.
with src as (
    select
        feature_id,
        properties as p,
        geom,
        loaded_at,
        row_number() over (partition by feature_id order by loaded_at desc) as rn
    from {{ source('raw', 'eccc_aqhi_forecasts') }}
    where properties ->> 'aqhi_type' = 'AQHI-Forecast'
)

select
    feature_id                                 as forecast_id,
    p ->> 'location_id'                        as location_id,
    p ->> 'location_name_en'                   as location_name_en,
    (p ->> 'publication_datetime')::timestamptz as published_at,
    (p ->> 'forecast_datetime')::timestamptz   as valid_at,
    extract(epoch from (p ->> 'forecast_datetime')::timestamptz
        - (p ->> 'publication_datetime')::timestamptz) / 3600 as lead_hours,
    (p ->> 'aqhi')::integer                    as aqhi,
    p ->> 'forecast_type'                      as forecast_type,
    geom,
    loaded_at
from src
where rn = 1
