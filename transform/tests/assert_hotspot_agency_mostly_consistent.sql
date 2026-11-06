-- Data-quality guard: at least 95% of Canadian hotspots should carry an agency code that
-- matches the province they fall in. A drop signals a geometry or source problem.
{{ config(severity='warn') }}
select
    count(*) filter (where agency_matches_province)::numeric / nullif(count(*), 0) as match_rate
from {{ ref('fct_hotspots') }}
having count(*) filter (where agency_matches_province)::numeric / nullif(count(*), 0) < 0.95
