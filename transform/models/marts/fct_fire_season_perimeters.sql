{{ config(post_hook="create index if not exists fct_fire_season_perimeters_geom_idx on {{ this }} using gist (geom_3347)") }}

-- Final perimeter of every Canadian fire in archived seasons, located in the census division
-- that contains a point on its surface. Complements dim_fire_perimeter_history (daily SCD2,
-- current seasons only): past seasons have final extents, not day-by-day growth.
select
    p.season_year,
    p.perimeter_uid,
    part.cduid,
    cd.province_code,
    p.hotspot_count,
    p.first_detected_at,
    p.last_detected_at,
    round(extract(epoch from p.last_detected_at - p.first_detected_at) / 86400, 1) as active_days,
    p.area_ha,
    p.geom_3347,
    ST_Transform(ST_SimplifyPreserveTopology(p.geom_3347, 100), 4326) as geom_4326
from {{ ref('stg_cwfis__season_perimeters') }} p
join lateral (
    select q.cduid
    from {{ ref('int_census_division_parts') }} q
    where ST_Intersects(q.geom_3347, ST_PointOnSurface(p.geom_3347))
    order by q.cduid
    limit 1
) part on true
join {{ ref('dim_census_division') }} cd on cd.cduid = part.cduid
