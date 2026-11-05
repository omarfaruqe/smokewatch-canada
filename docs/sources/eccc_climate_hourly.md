# Source: ECCC hourly climate observations (weather)

- **Publisher:** Environment and Climate Change Canada, MSC GeoMet
- **API:** `https://api.weather.gc.ca/collections/climate-hourly/items` (OGC API - Features)
- **Licence:** Open Government Licence - Canada
- **Bronze path:** `eccc/climate-hourly/date=YYYY-MM-DD/{items.geojson,_manifest.json}`
- **Query:** exact property filters `UTC_YEAR`, `UTC_MONTH`, `UTC_DAY` (verified: one partition
  spans `T00:00:00` to `T23:00:00` UTC). Published with a lag; the default day is yesterday.

## Observed profile (2026-11-04)

- 21,127 rows, 933 stations, all 13 provinces and territories
  (BC 3,405 · QC 3,392 · ON 2,927 · AB 1,791 · NU 1,729 · SK 1,525 · NT 1,417 · MB 1,394 ·
  NS 1,135 · NL 1,053 · YT 654 · NB 537 · PE 168)
- No duplicate `ID`, no duplicate (station, hour); 775 of 933 stations report all 24 hours
- Null rates: TEMP 1.1 %, RELATIVE_HUMIDITY 1.7 %, WIND_SPEED 3.4 %, PRECIP_AMOUNT 23.3 %,
  VISIBILITY 75.3 % (only some stations measure it)
- `*_FLAG` columns carry quality flags (e.g. `M` = missing); 126 TEMP rows flagged
- `WEATHER_ENG_DESC = 'Smoke'` appears (Fort Simpson A, NT; visibility 4 km), a direct
  ground-truth signal to validate hotspot/AQHI exposure

## Key fields

| Field | Meaning | Notes |
|---|---|---|
| `ID` | `<climate id>.<y>.<m>.<d>.<local hour>` | Unique per row |
| `CLIMATE_IDENTIFIER`, `STN_ID`, `STATION_NAME`, `PROVINCE_CODE` | Station | Natural key with `UTC_DATE` |
| `LATITUDE_DECIMAL_DEGREES`, `LONGITUDE_DECIMAL_DEGREES` | Location | Also in geometry |
| `UTC_DATE` | Observation hour, UTC | No `Z` suffix: parse as UTC |
| `LOCAL_DATE`, `LOCAL_*` | Local standard time | Not used for partitioning |
| `TEMP`, `DEW_POINT_TEMP`, `HUMIDEX`, `WINDCHILL` | degC | |
| `RELATIVE_HUMIDITY` | % | |
| `WIND_SPEED`, `WIND_DIRECTION` | km/h, tens of degrees | |
| `STATION_PRESSURE` | kPa | |
| `VISIBILITY` | km | Smoke indicator |
| `PRECIP_AMOUNT` | mm | |
| `WEATHER_ENG_DESC`, `WEATHER_FRE_DESC` | Present weather text | `NA`/`ND` when not reported |
