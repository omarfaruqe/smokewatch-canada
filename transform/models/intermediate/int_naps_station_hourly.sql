{{ config(post_hook="create index if not exists int_naps_station_hourly_idx on {{ this }} (naps_id, observed_at)") }}

-- One row per NAPS station per UTC hour with PM2.5 (ug/m3), O3 and NO2 (ppb).
-- Where a station runs several instruments for a pollutant, keep the method with the most
-- valid hours (ties broken by method code) so co-located monitors are not double counted.
with method_rank as (
    select
        naps_id, pollutant, method_code,
        row_number() over (
            partition by naps_id, pollutant order by count(value) desc, method_code
        ) as rn
    from {{ ref('stg_naps__hourly') }}
    group by naps_id, pollutant, method_code
)

select
    h.naps_id,
    h.observed_at,
    max(h.province_code)                       as province_code,
    max(h.value) filter (where h.pollutant = 'pm25') as pm25,
    max(h.value) filter (where h.pollutant = 'o3')   as o3,
    max(h.value) filter (where h.pollutant = 'no2')  as no2
from {{ ref('stg_naps__hourly') }} h
join method_rank m
    on m.naps_id = h.naps_id
   and m.pollutant = h.pollutant
   and m.method_code is not distinct from h.method_code
   and m.rn = 1
group by h.naps_id, h.observed_at
