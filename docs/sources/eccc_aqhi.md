# Source: ECCC Air Quality Health Index (AQHI)

- **Publisher:** Environment and Climate Change Canada, MSC GeoMet
- **API:** OGC API - Features at `https://api.weather.gc.ca` (paged via `rel=next` links)
- **Licence:** Open Government Licence - Canada

## aqhi-observations-realtime

- **Bronze path:** `eccc/aqhi-observations-realtime/date=YYYY-MM-DD/{items.geojson,_manifest.json}`
- **Query:** `datetime=<day>T00:00:00Z/<day>T23:59:59Z` filters on `observation_datetime` (verified)
- **Profile (2026-11-05, 00-20 UTC):** 2,535 rows, 124 locations, 21 hours; no duplicate `id`,
  no duplicate (location, hour), no null `aqhi`; 108 rows `observation_type = amendment`
- **Grain:** one row per location per hour. Natural key: (`location_id`, `observation_datetime`)
- **Late data:** amendments arrive after first publication, so the daily job re-pulls yesterday
- `latest` is snapshot-dependent (true for the newest hour at fetch time): exclude from facts

| Field | Meaning |
|---|---|
| `id` | e.g. `AQ_OBS-JAHJY-20261105170000` |
| `location_id`, `location_name_en`, `location_name_fr` | AQHI community |
| `observation_datetime` | Hour of observation (UTC) |
| `aqhi` | AQHI value (decimal) |
| `observation_type` | `original` or `amendment` |
| `special_notes_en/fr` | Free text, usually empty |

## aqhi-forecasts-realtime

- **Bronze path:** `eccc/aqhi-forecasts-realtime/pub_date=YYYY-MM-DD/{items.geojson,_manifest.json}`
- **Behaviour:** the API serves a rolling ~3-day window of publications (28 publications,
  27,360 rows on 2026-11-05). Each run splits by `publication_datetime` date and merges into
  the existing partition by `id` (new wins), so rows that age out of the window are kept.
- **Profile:** 134 locations; 1,710 rows `forecast_type = amendment`; no duplicate `id`
- **Two record shapes**, split in silver on `aqhi_type`:
  - `AQHI-Forecast` (26,640 rows): hourly; `forecast_datetime`, integer `aqhi`
  - `AQHI-Forecast-Period` (720 rows): `forecast_period.period_1..4` with
    `forecast_period_en/fr` (Today, Tonight, Tomorrow, Tomorrow Night), `aqhi` and
    `aqhi_insmoke` (AQHI under smoke conditions)
- **Lead time** = `forecast_datetime - publication_datetime` (useful for forecast-skill metrics)
