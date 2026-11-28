{{ config(indexes=[{'columns': ['geom_3347'], 'type': 'gist'}]) }}

-- First Nation locations published by Indigenous Services Canada: one point per band,
-- usually the band administrative office, in NAD83(CSRS) longitude/latitude. A band's
-- reserves can lie far from this point, so it locates the community only roughly.
select
    band_number::integer                       as band_number,
    band_name,
    ST_Transform(
        ST_SetSRID(ST_MakePoint(longitude::double precision, latitude::double precision), 4617),
        3347)::geometry(Point, 3347)           as geom_3347,
    ST_SetSRID(ST_MakePoint(longitude::double precision, latitude::double precision), 4326)
        ::geometry(Point, 4326)                as geom_4326
from {{ source('raw', 'isc_first_nations') }}
where nullif(longitude, '') is not null and nullif(latitude, '') is not null
