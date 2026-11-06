{{ config(materialized='table', post_hook="create index if not exists {{ this.name }}_geom_idx on {{ this }} using gist (geom_3347)") }}

-- 2021 dissemination areas (~57,000): population summed from dissemination blocks, located
-- by StatCan's representative point (already in EPSG:3347 Lambert coordinates).
select
    dauid,
    max(cduid)                                 as cduid,
    max(pruid)                                 as pruid,
    sum(nullif(db_pop_2021, '')::integer)      as population_2021,
    ST_SetSRID(ST_MakePoint(max(da_rp_x)::double precision, max(da_rp_y)::double precision), 3347)
        ::geometry(Point, 3347)                as geom_3347
from {{ source('raw', 'statcan_geo_attributes') }}
group by dauid
