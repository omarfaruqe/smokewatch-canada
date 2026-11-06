-- NAPS hourly values, unpivoted from H01..H24 to one row per station-hour.
-- NAPS hours are hour-ending in local STANDARD time all year (no daylight saving), so
-- UTC = local standard time - offset (e.g. 13:00 at offset -5 is 18:00 UTC).
-- -999 means no data; other negative values are treated as invalid.
with r as (
    select
        case pollutant when 'PM2.5' then 'pm25' when 'O3' then 'o3' when 'NO2' then 'no2'
            else lower(pollutant) end          as pollutant,
        method_code,
        lpad(naps_id, 6, '0')                  as naps_id,
        case province when 'YU' then 'YT' else province end as province_code,
        "date"::date                           as local_date,
        array[h01, h02, h03, h04, h05, h06, h07, h08, h09, h10, h11, h12,
              h13, h14, h15, h16, h17, h18, h19, h20, h21, h22, h23, h24] as hours
    from {{ source('raw', 'naps_hourly') }}
)

select
    r.pollutant,
    r.method_code,
    r.naps_id,
    r.province_code,
    ((r.local_date + u.hour_ending * interval '1 hour')
        - st.utc_offset_hours * interval '1 hour') at time zone 'UTC' as observed_at,
    case
        when u.raw_value ~ '^-?[0-9]+(\.[0-9]+)?$' and u.raw_value::numeric >= 0
        then u.raw_value::numeric
    end                                        as value
from r
join {{ ref('stg_naps__stations') }} st using (naps_id)
cross join lateral unnest(r.hours) with ordinality as u(raw_value, hour_ending)
