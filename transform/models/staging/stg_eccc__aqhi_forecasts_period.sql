-- Named-period AQHI forecasts (Today, Tonight, ...), unpivoted to one row per period.
with src as (
    select
        feature_id,
        properties as p,
        geom,
        loaded_at,
        row_number() over (partition by feature_id order by loaded_at desc) as rn
    from {{ source('raw', 'eccc_aqhi_forecasts') }}
    where properties ->> 'aqhi_type' = 'AQHI-Forecast-Period'
)

select
    s.feature_id                               as forecast_id,
    s.p ->> 'location_id'                      as location_id,
    s.p ->> 'location_name_en'                 as location_name_en,
    (s.p ->> 'publication_datetime')::timestamptz as published_at,
    substring(per.key from '\d+')::integer     as period_number,
    per.value ->> 'forecast_period_en'         as period_name_en,
    per.value ->> 'forecast_period_fr'         as period_name_fr,
    (per.value ->> 'aqhi')::integer            as aqhi,
    (per.value ->> 'aqhi_insmoke')::integer    as aqhi_in_smoke,
    s.p ->> 'forecast_type'                    as forecast_type,
    s.geom,
    s.loaded_at
from src s
cross join lateral jsonb_each(s.p -> 'forecast_period') as per(key, value)
where s.rn = 1
