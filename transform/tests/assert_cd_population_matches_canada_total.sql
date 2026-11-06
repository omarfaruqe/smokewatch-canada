-- Census divisions must add up to the official Canada total in table 98-10-0007-01.
with cd as (
    select sum(population_2021) as total from {{ ref('stg_statcan__census_divisions') }}
),
canada as (
    select population_2021::bigint as total
    from {{ source('raw', 'statcan_population_cd') }}
    where geo = 'Canada'
)
select * from cd, canada where cd.total <> canada.total
