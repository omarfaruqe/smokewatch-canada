{{ config(post_hook="create index if not exists dim_census_division_geom_idx on {{ this }} using gist (geom_3347)") }}

-- One row per 2021 census division, with province attributes and two geometries:
--   geom_3347  analysis geometry (50 m), used for spatial joins
--   geom_4326  display geometry (500 m, WGS84) for web maps
select
    cd.cduid,
    cd.dguid,
    cd.cd_name,
    cd.cd_type,
    cd.pruid,
    pc.postal_code                             as province_code,
    pc.name_en                                 as province_name_en,
    pc.name_fr                                 as province_name_fr,
    pc.region,
    cd.population_2021,
    cd.population_2016,
    cd.land_area_km2,
    cd.population_density_km2,
    cd.geom_3347,
    ST_Multi(ST_CollectionExtract(
        case when ST_IsValid(disp.g) then disp.g else ST_MakeValid(disp.g) end,
        3))::geometry(MultiPolygon, 4326)       as geom_4326
from {{ ref('stg_statcan__census_divisions') }} cd
join {{ ref('province_codes') }} pc using (pruid)
-- Simplifying at 500 m can make neighbouring rings touch, so repair after simplifying.
cross join lateral (
    select ST_Transform(ST_SimplifyPreserveTopology(cd.geom_3347, 500), 4326) as g
) disp
