-- How accurate ECCC's hourly AQHI forecasts are, by lead time, across all matched pairs.
--   mae / bias            mean absolute error and mean signed error (forecast - observed)
--   share_within_1        share of forecasts within 1 AQHI point of the observation
--   pod                   probability of detection: high-risk hours (rounded AQHI 7+) that
--                         were forecast as high risk
--   far                   false alarm ratio: high-risk forecasts that did not happen
-- pod is null when no high-risk hour was observed, far when none was forecast.
select
    lead_bucket,
    count(*)                                   as pairs,
    count(distinct location_id)                as locations,
    min(valid_at)                              as first_valid_at,
    max(valid_at)                              as last_valid_at,
    round(avg(abs(error)), 2)                  as mae,
    round(avg(error), 2)                       as bias,
    round(avg((abs(error) <= 1)::int), 3)      as share_within_1,
    count(*) filter (where forecast_high_risk and observed_high_risk)     as hits,
    count(*) filter (where not forecast_high_risk and observed_high_risk) as misses,
    count(*) filter (where forecast_high_risk and not observed_high_risk) as false_alarms,
    round(
        count(*) filter (where forecast_high_risk and observed_high_risk)::numeric
        / nullif(count(*) filter (where observed_high_risk), 0), 3)       as pod,
    round(
        count(*) filter (where forecast_high_risk and not observed_high_risk)::numeric
        / nullif(count(*) filter (where forecast_high_risk), 0), 3)       as far
from {{ ref('fct_aqhi_forecast_pairs') }}
group by lead_bucket
order by lead_bucket
