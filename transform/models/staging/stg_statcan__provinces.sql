{{ config(materialized='table', post_hook="create index if not exists {{ this.name }}_geom_idx on {{ this }} using gist (geom_3347)") }}

-- Provinces/territories for maps and roll-ups: simplified to 200 m, repaired only if invalid.
select
    pruid,
    dguid,
    prename                                    as name_en,
    prfname                                    as name_fr,
    preabbr                                    as abbr_en,
    prfabbr                                    as abbr_fr,
    landarea::numeric                          as land_area_km2,
    ST_Multi(ST_CollectionExtract(
        case when ST_IsValid(simp.g) then simp.g else ST_MakeValid(simp.g) end,
        3))::geometry(MultiPolygon, 3347)
                                               as geom_3347
from {{ source('raw', 'statcan_provinces') }}
cross join lateral (select ST_SimplifyPreserveTopology(geom, 200) as g) simp
