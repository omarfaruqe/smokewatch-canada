{{ config(materialized='table', post_hook="create index if not exists {{ this.name }}_geom_idx on {{ this }} using gist (geom_3347)") }}

-- 2021 census divisions with typed 2021 population.
-- Geometry is simplified to 50 m (well below satellite hotspot pixel size, 375-1000 m), then
-- repaired only where invalid. Full-detail ST_MakeValid exhausted Postgres memory.
select
    cd.cduid,
    cd.dguid,
    cd.cdname                                  as cd_name,
    cd.cdtype                                  as cd_type,
    cd.pruid,
    cd.landarea::numeric                       as land_area_km2,
    pop.population_2021::bigint                as population_2021,
    pop.population_2016::bigint                as population_2016,
    nullif(pop.population_density_per_square_kilometre_2021, '')::numeric
                                               as population_density_km2,
    ST_Multi(ST_CollectionExtract(
        case when ST_IsValid(simp.g) then simp.g else ST_MakeValid(simp.g) end,
        3))::geometry(MultiPolygon, 3347)
                                               as geom_3347
from {{ source('raw', 'statcan_census_divisions') }} cd
left join {{ source('raw', 'statcan_population_cd') }} pop
    on pop.dguid = cd.dguid
cross join lateral (select ST_SimplifyPreserveTopology(cd.geom, 50) as g) simp
