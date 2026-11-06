# Source: CWFIS past-season fire perimeters (archive)

- **Publisher:** Natural Resources Canada, CWFIS
- **URL:** `https://cwfis.cfs.nrcan.gc.ca/downloads/hotspots/archive/<YYYY>_perimeters.zip`
- **Licence:** Open Government Licence - Canada
- **Bronze:** `cwfis/perimeters_archive/year=YYYY/{YYYY_perimeters.zip,_manifest.json}`
- **Raw:** `raw.cwfis_season_perimeters` (source projection EPSG:3978, Canada Atlas Lambert)
- **Mart:** `fct_fire_season_perimeters` (EPSG:3347 + simplified WGS84, census division by
  point on surface)

## 2023 profile

- Shapefile `cc_apt_buf`: 1,144 polygons, all valid; fields `uid`, `hcount`, `firstdate`,
  `lastdate` (`YYYY/MM/DD HH:MM:SS`, UTC), `area` (ha), `consis_id`
- Fires from 2023-04-07 to 2023-10-29; **total area 16.0 million ha**, in line with official
  national totals for the record 2023 season

| Province | Fires | Area (M ha) | Largest (ha) |
|---|---|---|---|
| QC | 191 | 4.95 | 1,019,995 |
| NT | 184 | 3.74 | 1,319,148 |
| AB | 93 | 3.29 | 661,972 |
| BC | 254 | 1.79 | 510,213 |
| SK | 123 | 1.26 | 513,575 |
| ON | 89 | 0.41 | 51,685 |
| YT | 100 | 0.36 | 68,073 |

## Caveats

These are **M3 hotspot-derived perimeters** (buffered clusters of satellite detections), not
agency-mapped fire lines. Adjacent fires can merge into one polygon (hence 1.0-1.3 M ha
"largest fires", which are complexes), and each polygon is assigned to a single province by its
point on surface. National totals are robust; provincial and single-fire figures are estimates
(for example BC shows 1.79 M ha against roughly 2.8 M ha in BC Wildfire Service figures).
Past seasons have final extents only; day-by-day growth exists only from our own daily
snapshots (`dim_fire_perimeter_history`).
