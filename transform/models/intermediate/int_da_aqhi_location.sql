-- Each dissemination area's nearest AQHI location per source, kept only within
-- `da_station_max_km` (default 50 km). Areas farther away have no AQHI coverage for that
-- source: unknown air quality, not clean air.
{% set max_m = var('da_station_max_km', 50) * 1000 %}

select
    da.dauid,
    da.cduid,
    da.population_2021,
    src.aqhi_source,
    near.location_id,
    round(near.distance_m)                     as distance_m
from {{ ref('stg_statcan__dissemination_areas') }} da
cross join (values ('eccc_observed'), ('naps_computed')) as src(aqhi_source)
cross join lateral (
    select l.location_id, ST_Distance(l.geom_3347, da.geom_3347) as distance_m
    from {{ ref('int_aqhi_locations') }} l
    where l.aqhi_source = src.aqhi_source
    order by l.geom_3347 <-> da.geom_3347
    limit 1
) near
where near.distance_m <= {{ max_m }}
