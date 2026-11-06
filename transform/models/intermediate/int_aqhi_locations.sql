{{ config(post_hook="create index if not exists {{ this.name }}_geom_idx on {{ this }} using gist (geom_3347)") }}

-- Every location that reports AQHI, by source: ECCC communities (observed) and NAPS stations
-- that measure all three AQHI pollutants (computed).
select distinct on (location_id)
    'eccc_observed'::text                      as aqhi_source,
    location_id,
    ST_Transform(geom, 3347)::geometry(Point, 3347) as geom_3347
from {{ ref('stg_eccc__aqhi_observations') }}
where geom is not null
union all
select
    'naps_computed',
    'NAPS-' || s.naps_id,
    ST_Transform(s.geom, 3347)::geometry(Point, 3347)
from {{ ref('stg_naps__stations') }} s
where exists (select 1 from {{ ref('int_naps_aqhi_hourly') }} a where a.naps_id = s.naps_id)
