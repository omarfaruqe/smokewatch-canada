-- Exposed population can never exceed the division's population.
select * from {{ ref('fct_daily_exposure') }}
where population_exposed_high_risk > population_2021
