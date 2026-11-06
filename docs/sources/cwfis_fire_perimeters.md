# Source: CWFIS current fire perimeters (M3 polygons)

- **Publisher:** Natural Resources Canada, CWFIS
- **Endpoint:** `https://cwfis.cfs.nrcan.gc.ca/geoserver/public/ows`, layer `public:m3_polygons_current`
  (season layer: `public:m3polygons`; final burned area: `public:nbac`)
- **Licence:** Open Government Licence - Canada
- **Bronze path:** `cwfis/perimeters/m3_polygons_current/date=YYYY-MM-DD/{items.geojson,_manifest.json}`
  (one snapshot per UTC day; same-day re-runs overwrite)

## Observed profile (first snapshot, 2026-11-06 UTC)

- 739 polygons, North America (filtered to Canada in dbt by point-on-surface in a census division)
- Feature id like `m3_polygons_current.228657`, used as `perimeter_id`

| Field | Meaning |
|---|---|
| `hcount` | Number of hotspots clustered into the perimeter |
| `firstdate`, `lastdate` | First and latest hotspot detection (UTC) |
| `area` | Area, ha |

## History (SCD Type 2)

The layer only shows the current state, so `dim_fire_perimeter_history` derives versions from
the sequence of daily snapshots: a new version whenever the hash of `hcount`, `area`,
`lastdate` and geometry changes. `valid_to` is exclusive and null while current; perimeters
dropped from the layer are closed the day after their last snapshot.

**Assumption to verify:** CWFIS keeps a perimeter's feature id stable across days. Once
several snapshots exist, check id carry-over between consecutive days; if ids are reissued,
switch to matching perimeters by spatial overlap.
