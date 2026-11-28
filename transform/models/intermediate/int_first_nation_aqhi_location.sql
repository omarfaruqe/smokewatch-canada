-- Each First Nation's nearest AQHI location per source within `da_station_max_km`
-- (default 50 km). Bands with no location in range for a source get no row for it.
{% set max_m = var('da_station_max_km', 50) * 1000 %}

select
    fn.band_number,
    fn.band_name,
    fn.cduid,
    fn.province_code,
    src.aqhi_source,
    near.location_id,
    round(near.distance_m)                     as distance_m
from {{ ref('dim_first_nation') }} fn
cross join (values ('eccc_observed'), ('naps_computed')) as src(aqhi_source)
cross join lateral (
    select l.location_id, ST_Distance(l.geom_3347, fn.geom_3347) as distance_m
    from {{ ref('int_aqhi_locations') }} l
    where l.aqhi_source = src.aqhi_source
    order by l.geom_3347 <-> fn.geom_3347
    limit 1
) near
where near.distance_m <= {{ max_m }}
