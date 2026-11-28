-- Each First Nation location's census division (containing, or nearest when just offshore)
-- and its nearest AQHI location per source within `da_station_max_km` (default 50 km).
-- Bands with no location in range for a source get no row for that source.
{% set max_m = var('da_station_max_km', 50) * 1000 %}

with division as (
    select fn.band_number, nearest.cduid
    from {{ ref('stg_isc__first_nations') }} fn
    cross join lateral (
        select p.cduid
        from {{ ref('int_census_division_parts') }} p
        order by p.geom_3347 <-> fn.geom_3347
        limit 1
    ) nearest
)

select
    fn.band_number,
    fn.band_name,
    d.cduid,
    src.aqhi_source,
    near.location_id,
    round(near.distance_m)                     as distance_m
from {{ ref('stg_isc__first_nations') }} fn
join division d using (band_number)
cross join (values ('eccc_observed'), ('naps_computed')) as src(aqhi_source)
cross join lateral (
    select l.location_id, ST_Distance(l.geom_3347, fn.geom_3347) as distance_m
    from {{ ref('int_aqhi_locations') }} l
    where l.aqhi_source = src.aqhi_source
    order by l.geom_3347 <-> fn.geom_3347
    limit 1
) near
where near.distance_m <= {{ max_m }}
