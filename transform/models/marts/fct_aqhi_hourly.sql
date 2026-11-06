{{ config(indexes=[{'columns': ['observed_date_utc', 'cduid'], 'type': 'btree'}]) }}

-- Hourly AQHI from two sources, with census division and Health Canada risk category:
--   eccc_observed   AQHI published by ECCC (recent days, from the realtime API)
--   naps_computed   AQHI computed from NAPS archive measurements (historical seasons)
-- Risk bands apply to the rounded AQHI: 1-3 low, 4-6 moderate, 7-10 high, above 10 very high.
with unioned as (
    select
        'eccc_observed'::text                  as aqhi_source,
        location_id,
        location_name_en,
        location_name_fr,
        observed_at,
        aqhi,
        observation_type,
        geom
    from {{ ref('stg_eccc__aqhi_observations') }}

    union all

    select
        'naps_computed',
        'NAPS-' || n.naps_id,
        st.station_name,
        st.station_name,
        n.observed_at,
        n.aqhi,
        'computed',
        st.geom
    from {{ ref('int_naps_aqhi_hourly') }} n
    join {{ ref('stg_naps__stations') }} st using (naps_id)
)

select
    u.aqhi_source,
    u.location_id,
    u.location_name_en,
    u.location_name_fr,
    u.observed_at,
    (u.observed_at at time zone 'UTC')::date   as observed_date_utc,
    lc.cduid,
    cd.province_code,
    u.aqhi,
    case
        when round(u.aqhi) <= 3 then 'low'
        when round(u.aqhi) <= 6 then 'moderate'
        when round(u.aqhi) <= 10 then 'high'
        else 'very_high'
    end                                        as risk_category,
    u.observation_type,
    u.geom
from unioned u
join {{ ref('int_location_census_division') }} lc
    on lc.point_type = case u.aqhi_source when 'eccc_observed' then 'aqhi' else 'naps' end
   and lc.point_id = case u.aqhi_source when 'eccc_observed' then u.location_id
                          else substring(u.location_id from 6) end
join {{ ref('dim_census_division') }} cd using (cduid)
