-- One row per location per hour. Prefer amendments, then the most recent load.
with src as (
    select
        properties as p,
        geom,
        loaded_at,
        row_number() over (
            partition by properties ->> 'location_id', properties ->> 'observation_datetime'
            order by (properties ->> 'observation_type' = 'amendment') desc, loaded_at desc
        ) as rn
    from {{ source('raw', 'eccc_aqhi_observations') }}
)

select
    p ->> 'location_id'                        as location_id,
    p ->> 'location_name_en'                   as location_name_en,
    p ->> 'location_name_fr'                   as location_name_fr,
    (p ->> 'observation_datetime')::timestamptz as observed_at,
    (p ->> 'aqhi')::numeric                    as aqhi,
    p ->> 'observation_type'                   as observation_type,
    nullif(p ->> 'special_notes_en', '')       as special_notes_en,
    geom,
    loaded_at
from src
where rn = 1
