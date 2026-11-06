-- Assigns every AQHI community and weather station to a census division: the division that
-- contains the point, or the nearest one for points just offshore (distance_m > 0).
with points as (
    (select distinct on (location_id)
        'aqhi'::text as point_type, location_id as point_id, ST_Transform(geom, 3347) as geom
    from {{ ref('stg_eccc__aqhi_observations') }}
    where geom is not null
    order by location_id, observed_at desc)
    union all
    (select distinct on (climate_id)
        'weather'::text, climate_id, ST_Transform(geom, 3347)
    from {{ ref('stg_eccc__weather_hourly') }}
    where geom is not null
    order by climate_id, observed_at desc)
)

select
    p.point_type,
    p.point_id,
    nearest.cduid,
    round(ST_Distance(p.geom, nearest.geom_3347)::numeric, 0) as distance_m
from points p
cross join lateral (
    select cd.cduid, cd.geom_3347
    from {{ ref('dim_census_division') }} cd
    order by cd.geom_3347 <-> p.geom
    limit 1
) nearest
