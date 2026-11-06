-- Dissemination areas (summed from blocks) must add up to the official Canada total.
with da as (select sum(population_2021) as total from {{ ref('stg_statcan__dissemination_areas') }}),
canada as (
    select population_2021::bigint as total
    from {{ source('raw', 'statcan_population_cd') }} where geo = 'Canada'
)
select * from da, canada where da.total <> canada.total
