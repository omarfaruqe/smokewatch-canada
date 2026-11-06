{{ config(indexes=[{'columns': ['geom_3347'], 'type': 'gist'}]) }}

-- Census divisions cut into pieces of at most 255 vertices for fast point-in-polygon joins.
-- Detailed coastlines (BC, Nunavut) make whole-polygon tests slow; small pieces keep each
-- test cheap and make the GiST index far more selective.
select
    cduid,
    ST_Subdivide(geom_3347, 255)::geometry(Polygon, 3347) as geom_3347
from {{ ref('dim_census_division') }}
