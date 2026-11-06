-- One row per census division per UTC day observed in any source (a full grid, so "no fire,
-- clean air" days are explicit zeros, not missing rows).
--
-- Exposure is estimated at census-division level: if any AQHI community in the division
-- reached a high-risk hour (rounded AQHI >= 7) that day, the division's 2021 population counts as
-- exposed. Divisions with no AQHI community have aqhi_coverage = false and null AQHI metrics.
with days as (
    select detected_date_utc as day from {{ ref('fct_hotspots') }}
    union
    select observed_date_utc from {{ ref('fct_aqhi_hourly') }}
),

fire as (
    select
        cduid,
        detected_date_utc                      as day,
        count(*)                               as hotspot_count,
        round(sum(frp_mw), 1)                  as total_frp_mw,
        max(fwi)                               as max_fwi
    from {{ ref('fct_hotspots') }}
    group by 1, 2
),

air as (
    select
        cduid,
        observed_date_utc                      as day,
        max(aqhi)                              as max_aqhi,
        round(avg(aqhi), 2)                    as mean_aqhi,
        count(*) filter (where risk_category in ('high', 'very_high')) as high_risk_hours,
        count(distinct location_id)            as aqhi_locations
    from {{ ref('fct_aqhi_hourly') }}
    group by 1, 2
),

smoke as (
    select
        lc.cduid,
        (w.observed_at at time zone 'UTC')::date as day,
        count(*)                               as smoke_report_hours
    from {{ ref('stg_eccc__weather_hourly') }} w
    join {{ ref('int_location_census_division') }} lc
        on lc.point_type = 'weather' and lc.point_id = w.climate_id
    where w.smoke_reported
    group by 1, 2
)

select
    cd.cduid,
    d.day,
    cd.cd_name,
    cd.province_code,
    cd.population_2021,
    coalesce(f.hotspot_count, 0)               as hotspot_count,
    coalesce(f.total_frp_mw, 0)                as total_frp_mw,
    f.max_fwi,
    a.aqhi_locations is not null               as aqhi_coverage,
    a.max_aqhi,
    a.mean_aqhi,
    coalesce(a.high_risk_hours, 0)             as high_risk_hours,
    coalesce(s.smoke_report_hours, 0)          as smoke_report_hours,
    case when a.high_risk_hours > 0 then cd.population_2021 else 0 end
                                               as population_exposed_high_risk
from {{ ref('dim_census_division') }} cd
cross join days d
left join fire f  on f.cduid = cd.cduid and f.day = d.day
left join air a   on a.cduid = cd.cduid and a.day = d.day
left join smoke s on s.cduid = cd.cduid and s.day = d.day
