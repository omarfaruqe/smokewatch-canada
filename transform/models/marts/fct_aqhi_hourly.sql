-- Hourly AQHI observations with census division and Health Canada risk category.
-- Risk bands apply to the rounded AQHI: 1-3 low, 4-6 moderate, 7-10 high, above 10 very high.
select
    o.location_id,
    o.location_name_en,
    o.location_name_fr,
    o.observed_at,
    (o.observed_at at time zone 'UTC')::date   as observed_date_utc,
    lc.cduid,
    cd.province_code,
    o.aqhi,
    case
        when round(o.aqhi) <= 3 then 'low'
        when round(o.aqhi) <= 6 then 'moderate'
        when round(o.aqhi) <= 10 then 'high'
        else 'very_high'
    end                                        as risk_category,
    o.observation_type,
    o.geom
from {{ ref('stg_eccc__aqhi_observations') }} o
join {{ ref('int_location_census_division') }} lc
    on lc.point_type = 'aqhi' and lc.point_id = o.location_id
join {{ ref('dim_census_division') }} cd using (cduid)
