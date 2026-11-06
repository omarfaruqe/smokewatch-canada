{{ config(post_hook="create index if not exists dim_fire_perimeter_history_geom_idx on {{ this }} using gist (geom)") }}

-- SCD Type 2 history of Canadian fire perimeters, derived from daily bronze snapshots.
--
-- A new version starts on the first snapshot where a perimeter's hash differs from the
-- previous one. valid_to is exclusive: the next version's valid_from, or the day after the
-- last snapshot that still contained the perimeter (it was dropped from the current layer).
-- Built from the full snapshot sequence, so it is deterministic and rebuildable from bronze.
--
-- Assumes CWFIS keeps a perimeter's feature id stable across days (see source docs).
with snaps as (
    select
        *,
        lag(row_hash) over (partition by perimeter_id order by snapshot_date) as prev_hash
    from {{ ref('stg_cwfis__fire_perimeters') }}
),

changes as (
    select
        *,
        lead(snapshot_date) over (partition by perimeter_id order by snapshot_date) as next_change
    from snaps
    where prev_hash is distinct from row_hash
),

seen as (
    select perimeter_id, max(snapshot_date) as last_seen
    from {{ ref('stg_cwfis__fire_perimeters') }}
    group by 1
),

latest as (
    select max(snapshot_date) as latest_snapshot from {{ ref('stg_cwfis__fire_perimeters') }}
),

canadian as (
    -- Locate each perimeter by a point guaranteed to lie on its surface.
    select distinct on (c.perimeter_id)
        c.perimeter_id, cd.cduid, cd.province_code
    from changes c
    join {{ ref('dim_census_division') }} cd
        on ST_Intersects(cd.geom_3347, ST_Transform(ST_PointOnSurface(c.geom), 3347))
    order by c.perimeter_id, c.snapshot_date desc
)

select
    c.perimeter_id,
    row_number() over (partition by c.perimeter_id order by c.snapshot_date) as version,
    c.snapshot_date                            as valid_from,
    coalesce(
        c.next_change,
        case when s.last_seen < l.latest_snapshot then s.last_seen + 1 end
    )                                          as valid_to,
    (c.next_change is null and s.last_seen = l.latest_snapshot) as is_current,
    ca.cduid,
    ca.province_code,
    c.hotspot_count,
    c.first_detected_at,
    c.last_detected_at,
    c.area_ha,
    c.row_hash,
    c.geom
from changes c
join seen s using (perimeter_id)
cross join latest l
join canadian ca using (perimeter_id)
