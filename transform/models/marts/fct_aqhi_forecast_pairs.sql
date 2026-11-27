{{ config(indexes=[{'columns': ['location_id', 'valid_at'], 'type': 'btree'}]) }}

-- Each ECCC hourly AQHI forecast matched with the observation for the same community and hour.
-- One location-hour is usually forecast several times (successive publications), so it can
-- appear in several pairs, each with its own lead time. Only forecasts issued before the hour
-- they forecast count (lead_hours > 0).
select
    f.forecast_id,
    f.location_id,
    o.location_name_en,
    o.cduid,
    o.province_code,
    f.published_at,
    f.valid_at,
    f.lead_hours,
    case
        when f.lead_hours <= 6 then '00-06h'
        when f.lead_hours <= 12 then '06-12h'
        when f.lead_hours <= 24 then '12-24h'
        when f.lead_hours <= 48 then '24-48h'
        else '48h+'
    end                                        as lead_bucket,
    f.aqhi                                     as forecast_aqhi,
    o.aqhi                                     as observed_aqhi,
    round(f.aqhi - o.aqhi, 2)                  as error,
    f.aqhi >= 7                                as forecast_high_risk,
    round(o.aqhi) >= 7                         as observed_high_risk
from {{ ref('stg_eccc__aqhi_forecasts_hourly') }} f
join {{ ref('fct_aqhi_hourly') }} o
    on o.aqhi_source = 'eccc_observed'
   and o.location_id = f.location_id
   and o.observed_at = f.valid_at
where f.lead_hours > 0
