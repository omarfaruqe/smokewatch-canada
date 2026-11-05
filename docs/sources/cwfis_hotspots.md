# Source: CWFIS satellite fire hotspots

- **Publisher:** Natural Resources Canada, Canadian Wildland Fire Information System (CWFIS)
- **Endpoint:** `https://cwfis.cfs.nrcan.gc.ca/geoserver/public/ows` (WFS 2.0.0, GeoJSON)
- **Layers:** `public:hotspots_24h` (rolling last 24 h), `public:hotspots` (season, filter on `rep_date`)
- **Licence:** Open Government Licence - Canada
- **Bronze path:** `cwfis/hotspots/<layer>/date=YYYY-MM-DD/{hotspots.geojson,_manifest.json}`

## Observed profile (first live pull, 2026-11-05)

- 2,711 point features, all with a unique `uid`
- Coverage is **North America**, not just Canada (lon -128.8 to -54.1, lat 25.0 to 58.6);
  717 of 2,711 had a Canadian `agency` (BC, AB, SK, MB, NL). Silver must filter to Canada
  (spatial join to StatCan boundaries; `agency` as a cross-check).
- `rep_date` spans about 24 h (UTC, ISO 8601 with `Z`)
- Sources: NASA (VIIRS-I, MODIS) and EUMETSAT (SLSTR); `satellite` is null for some SLSTR rows

## Attributes

| Field | Meaning | Notes |
|---|---|---|
| `uid` | Hotspot identifier | Natural key |
| `lat`, `lon` | Location (WGS84) | Duplicates geometry |
| `rep_date` | Detection time (UTC) | Partition/incremental key |
| `source`, `sensor`, `satellite` | Detection provenance | e.g. NASA_w / VIIRS-I / NOAA-20 |
| `agency` | Province/territory, US state, or country code | Not Canada-only |
| `temp`, `rh`, `ws`, `wd`, `pcp` | Weather at the hotspot | degC, %, km/h, deg, mm |
| `ffmc`, `dmc`, `dc`, `isi`, `bui`, `fwi` | Canadian Fire Weather Index components | |
| `ros`, `hfi`, `sfc`, `tfc`, `bfc`, `cfb` | Fire behaviour estimates | rate of spread, head fire intensity, fuel consumption, crown fraction burned |
| `frp` | Fire radiative power | MW |
| `estarea` | Estimated area | ha |
| `fuel`, `elev`, `ecozone`, `pconif` | Fuel type, elevation, ecozone, % conifer | `fuel` often null |
| `scan_px_size`, `track_px_size`, `px_size` | Pixel footprint | m |
| `m3_confidence` | Detection confidence | |
| `today`, `age` | Server snapshot date and hotspot age (h) | Snapshot-dependent: exclude from facts |
