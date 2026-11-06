-- One row per fire perimeter per daily snapshot. row_hash detects any change in the
-- perimeter's attributes or shape between snapshots (used to build SCD Type 2 history).
select
    feature_id                                 as perimeter_id,
    substring(partition from 'date=(\d{4}-\d{2}-\d{2})')::date as snapshot_date,
    (properties ->> 'hcount')::integer         as hotspot_count,
    (properties ->> 'firstdate')::timestamptz  as first_detected_at,
    (properties ->> 'lastdate')::timestamptz   as last_detected_at,
    (properties ->> 'area')::numeric           as area_ha,
    geom,
    md5(concat_ws('|',
        properties ->> 'hcount', properties ->> 'area', properties ->> 'lastdate',
        encode(ST_AsBinary(geom), 'hex')))     as row_hash,
    loaded_at
from {{ source('raw', 'cwfis_fire_perimeters') }}
where feature_id is not null
