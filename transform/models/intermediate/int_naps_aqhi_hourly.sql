-- AQHI computed from NAPS measurements with Health Canada's formula (Stieb et al., 2008):
--   AQHI = (10/10.4) * 100 * [ (exp(0.000871*NO2) - 1) + (exp(0.000537*O3) - 1)
--                              + (exp(0.000487*PM2.5) - 1) ]
-- using 3-hour rolling means (NO2, O3 in ppb; PM2.5 in ug/m3). A mean needs at least 2 of
-- the 3 hours; AQHI is only computed where all three pollutants are available.
with rolling as (
    select
        naps_id,
        observed_at,
        province_code,
        pm25,
        avg(pm25) over w   as pm25_3h, count(pm25) over w as pm25_n,
        avg(o3) over w     as o3_3h,   count(o3) over w   as o3_n,
        avg(no2) over w    as no2_3h,  count(no2) over w  as no2_n
    from {{ ref('int_naps_station_hourly') }}
    window w as (partition by naps_id order by observed_at
                 range between interval '2 hours' preceding and current row)
)

select
    naps_id,
    observed_at,
    province_code,
    pm25,
    round(pm25_3h, 1)                          as pm25_3h,
    round(o3_3h, 1)                            as o3_3h,
    round(no2_3h, 1)                           as no2_3h,
    round((10 / 10.4 * 100 * (
          (exp(0.000871 * no2_3h) - 1)
        + (exp(0.000537 * o3_3h) - 1)
        + (exp(0.000487 * pm25_3h) - 1)))::numeric, 2) as aqhi
from rolling
where pm25_n >= 2 and o3_n >= 2 and no2_n >= 2
