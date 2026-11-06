{{ config(
    materialized='incremental',
    unique_key='hotspot_id',
    incremental_strategy='delete+insert',
    on_schema_change='append_new_columns',
    indexes=[{'columns': ['detected_date_utc'], 'type': 'btree'}, {'columns': ['geom'], 'type': 'gist'}],
) }}

-- Incremental on the staging loaded_at watermark.
-- Canadian satellite hotspots: CWFIS covers North America, so keep only detections that
-- fall inside a 2021 census division. The join uses subdivided division pieces for speed;
-- a point on a piece boundary can match twice, so keep one match per hotspot. agency_matches_province cross-checks the source's own
-- jurisdiction code (PC = Parks Canada, which spans provinces).
select
    h.hotspot_id,
    h.detected_at,
    h.detected_date_utc,
    cd.cduid,
    cd.province_code,
    h.agency,
    (h.agency = cd.province_code or h.agency = 'PC') as agency_matches_province,
    h.detection_source,
    h.sensor,
    h.satellite,
    h.frp_mw,
    h.est_area_ha,
    h.head_fire_intensity,
    h.rate_of_spread,
    h.fwi,
    h.isi,
    h.bui,
    h.ffmc,
    h.dmc,
    h.dc,
    h.temp_c,
    h.rh_pct,
    h.wind_speed_kmh,
    h.fuel_type,
    h.ecozone,
    h.confidence,
    h.geom,
    h.loaded_at
from {{ ref('stg_cwfis__hotspots') }} h
join lateral (
    select p.cduid
    from {{ ref('int_census_division_parts') }} p
    where ST_Intersects(p.geom_3347, h.geom_3347)
    order by p.cduid
    limit 1
) part on true
join {{ ref('dim_census_division') }} cd on cd.cduid = part.cduid
{% if is_incremental() %}
where h.loaded_at > (select coalesce(max(loaded_at), '-infinity') from {{ this }})
{% endif %}
