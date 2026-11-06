-- Canadian satellite hotspots: CWFIS covers North America, so keep only detections that
-- fall inside a 2021 census division. agency_matches_province cross-checks the source's own
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
    h.geom
from {{ ref('stg_cwfis__hotspots') }} h
join {{ ref('dim_census_division') }} cd
    on ST_Intersects(cd.geom_3347, ST_Transform(h.geom, 3347))
