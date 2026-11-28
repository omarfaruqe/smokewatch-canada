{{ config(
    materialized='incremental',
    unique_key=['band_number', 'day'],
    incremental_strategy='delete+insert',
    on_schema_change='append_new_columns',
    indexes=[{'columns': ['day']}],
) }}

{#- Same lookback as fct_daily_exposure: incremental runs recompute the last
    `exposure_lookback_days` days. -#}
{% set since %}
    {% if is_incremental() %}
        (select max(day) - {{ var('exposure_lookback_days', 3) }} from {{ this }})
    {% else %}
        '-infinity'::date
    {% endif %}
{% endset %}

-- One row per First Nation per UTC day on which its nearest AQHI location (within the
-- cap, either source) reported. high_risk is true when either nearest location had a
-- high-risk hour (rounded AQHI >= 7). Days with no report are missing rows: unknown air
-- quality, not clean air.
with loc_day as (
    select
        aqhi_source,
        location_id,
        observed_date_utc                      as day,
        max(aqhi)                              as max_aqhi,
        count(*) filter (where risk_category in ('high', 'very_high')) as high_risk_hours
    from {{ ref('fct_aqhi_hourly') }}
    where observed_date_utc >= {{ since }}
    group by 1, 2, 3
)

select
    fl.band_number,
    ld.day,
    max(fl.band_name)                          as band_name,
    max(fl.cduid)                              as cduid,
    max(fl.province_code)                      as province_code,
    max(ld.max_aqhi)                           as max_aqhi,
    max(ld.high_risk_hours)                    as high_risk_hours,
    max(ld.high_risk_hours) > 0                as high_risk,
    min(fl.distance_m)                         as nearest_distance_m
from {{ ref('int_first_nation_aqhi_location') }} fl
join loc_day ld
    on ld.aqhi_source = fl.aqhi_source and ld.location_id = fl.location_id
group by fl.band_number, ld.day
