{{ config(indexes=[{'columns': ['band_number'], 'unique': True}]) }}

-- First Nations (ISC locations) with their census division: the one containing the band
-- point, or the nearest one when the point lies just outside every division.
select
    fn.band_number,
    fn.band_name,
    nearest.cduid,
    cd.province_code,
    fn.geom_3347,
    fn.geom_4326
from {{ ref('stg_isc__first_nations') }} fn
cross join lateral (
    select p.cduid
    from {{ ref('int_census_division_parts') }} p
    order by p.geom_3347 <-> fn.geom_3347
    limit 1
) nearest
join {{ ref('dim_census_division') }} cd on cd.cduid = nearest.cduid
