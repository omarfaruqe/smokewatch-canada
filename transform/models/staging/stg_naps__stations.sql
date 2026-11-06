-- NAPS stations. Timezone_UTC is the standard-time offset NAPS uses for all hourly data.
select
    lpad(naps_id, 6, '0')                      as naps_id,
    station_name,
    city,
    upper(province_territory_en)               as province_name_en,
    nullif(timezone_utc, '')::numeric          as utc_offset_hours,
    nullif(latitude, '')::numeric              as latitude,
    nullif(longitude, '')::numeric             as longitude,
    ST_SetSRID(ST_MakePoint(nullif(longitude, '')::numeric, nullif(latitude, '')::numeric), 4326)
                                               as geom
from {{ source('raw', 'naps_stations') }}
where nullif(latitude, '') is not null
