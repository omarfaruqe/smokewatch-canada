-- Final fire perimeters of past seasons from the CWFIS archive, reprojected from EPSG:3978
-- (Canada Atlas Lambert) to EPSG:3347. Archive dates have no zone marker and are UTC.
select
    season_year,
    uid                                        as perimeter_uid,
    hcount::integer                            as hotspot_count,
    to_timestamp(firstdate, 'YYYY/MM/DD HH24:MI:SS') at time zone 'UTC' as first_detected_at,
    to_timestamp(lastdate,  'YYYY/MM/DD HH24:MI:SS') at time zone 'UTC' as last_detected_at,
    area::numeric                              as area_ha,
    consis_id,
    ST_Transform(geom, 3347)                   as geom_3347
from {{ source('raw', 'cwfis_season_perimeters') }}
