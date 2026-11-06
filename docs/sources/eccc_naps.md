# Source: ECCC National Air Pollution Surveillance (NAPS) archive

- **Publisher:** Environment and Climate Change Canada
- **Access:** ECCC data portal API: `https://data-donnees.az.ec.gc.ca/api/path_contents?path=...`
  (folder listing, JSON) and `.../api/file?path=...` (download)
- **Licence:** Open Government Licence - Canada
- **Bronze:** `naps/hourly/<POLLUTANT>/year=YYYY/<POLLUTANT>_YYYY.csv` + manifest (re-downloaded
  only when the portal's `last_modified` changes); `naps/stations/StationsNAPS-StationsSNPA.csv`
- **Raw:** `raw.naps_hourly` (wide, text), `raw.naps_stations`

## File layout

- Bilingual preamble, then a header row starting `Pollutant//Polluant`
- One row per pollutant x method x station x **local standard date**, values in `H01..H24`
  (**hour ending, local standard time all year, no daylight saving**)
- `-999` = no data; `0` is valid
- PM2.5 in ug/m3; O3 and NO2 in ppb
- **Columns differ by pollutant:** PM2.5 has `Method Code`, NO2 does not; NO2 also drops the
  leading zero of NAPS IDs. The loader maps columns by header name and pads IDs to 6 digits.
- Co-located instruments produce several rows per station-day (24,090 for PM2.5 in 2023);
  dbt keeps the method with the most valid hours per station and pollutant
- Yukon is coded `YU` (mapped to `YT`)

## Stations file

- Several `**********Section**********` blocks; the first holds 636 stations
- `Timezone_UTC` gives each station's standard offset (-8 to -3.5), used for UTC conversion
- `CD` is a census division *name*, not a code, so stations are mapped spatially

## 2023 profile

| Pollutant | Station-days | Stations |
|---|---|---|
| PM2.5 | 110,595 | 231 |
| O3 | 84,680 | |
| NO2 | 69,350 | |

## Computed AQHI (`int_naps_aqhi_hourly`)

Health Canada formula (Stieb et al., 2008) on 3-hour rolling means (at least 2 of 3 hours):

    AQHI = (10/10.4) * 100 * [ (e^(0.000871 NO2) - 1) + (e^(0.000537 O3) - 1) + (e^(0.000487 PM2.5) - 1) ]

**Validation:** on 2023-06-25, during the Quebec wildfire smoke event, computed AQHI reached
15-17 at Montreal-area stations (Terrebonne 16.8, Montreal York/Roberval 16.4, Longueuil 16.0)
with 9-14 high-risk hours, consistent with the "10+, very high risk" readings ECCC reported.
