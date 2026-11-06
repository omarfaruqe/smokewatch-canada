-- SCD Type 2 integrity: per perimeter, at most one current version, intervals never overlap,
-- valid_to is after valid_from, and only the last version may be open-ended.
with v as (
    select
        *,
        lead(valid_from) over (partition by perimeter_id order by version) as next_from,
        count(*) filter (where is_current) over (partition by perimeter_id) as current_versions
    from {{ ref('dim_fire_perimeter_history') }}
)
select * from v
where current_versions > 1
   or (valid_to is not null and valid_to <= valid_from)
   or (next_from is not null and (valid_to is null or valid_to <> next_from))
   or (is_current and valid_to is not null)
