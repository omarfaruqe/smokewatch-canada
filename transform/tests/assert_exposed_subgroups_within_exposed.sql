-- Seniors, young children and Indigenous identity exposed in a division-day are parts of
-- the exposed population, so none may exceed population_exposed_high_risk_da.
select cduid, day
from {{ ref('fct_daily_exposure') }}
where seniors_exposed_high_risk_da > population_exposed_high_risk_da
   or children_exposed_high_risk_da > population_exposed_high_risk_da
   or indigenous_exposed_high_risk_da > population_exposed_high_risk_da
