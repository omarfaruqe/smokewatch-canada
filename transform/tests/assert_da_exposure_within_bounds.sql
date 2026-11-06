-- The nearest-station estimate can never exceed the covered population, and covered
-- population can never exceed the division's population.
select * from {{ ref('fct_daily_exposure') }}
where population_exposed_high_risk_da > population_aqhi_covered_da
   or population_aqhi_covered_da > population_2021
