-- 2021 Census Profile counts per dissemination area, one row per area. Suppressed values
-- (empty OBS_VALUE with a flag) stay null. Ages are 100% data; Indigenous identity comes
-- from the 25% sample (population in private households) and is randomly rounded.
select
    dauid,
    max(nullif(obs_value, '')::numeric) filter (where characteristic = '1')::integer
                                               as profile_population_2021,
    max(nullif(obs_value, '')::numeric) filter (where characteristic = '10')::integer
                                               as age_0_4,
    max(nullif(obs_value, '')::numeric) filter (where characteristic = '24')::integer
                                               as age_65_plus,
    max(nullif(obs_value, '')::numeric) filter (where characteristic = '1389')::integer
                                               as indigenous_identity
from {{ source('raw', 'statcan_profile_da') }}
group by dauid
