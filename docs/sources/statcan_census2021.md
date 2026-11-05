# Source: Statistics Canada 2021 Census boundaries and population

- **Publisher:** Statistics Canada
- **Licence:** Statistics Canada Open Licence
- **Bronze:** `statcan/census2021/boundaries/*.zip`, `statcan/census2021/tables/98100007-eng.zip`
  (static; downloaded once with a sha256 manifest)
- **Raw tables:** `raw.statcan_census_divisions`, `raw.statcan_provinces`, `raw.statcan_population_cd`
  (replaced on each `smokewatch load census`)

## Boundary files (cartographic, Shapefile)

File names follow StatCan's convention, e.g. `lcd_000b21a_e` = Lambert projection, census
division, Canada (000), cartographic (b), 2021, Shapefile (a), English.

| Table | Rows | Fields | CRS |
|---|---|---|---|
| `raw.statcan_census_divisions` | 293 | `cduid`, `dguid`, `cdname`, `cdtype`, `landarea`, `pruid`, `geom` | EPSG:3347 |
| `raw.statcan_provinces` | 13 | `pruid`, `dguid`, `prname`, `prename`, `prfname`, `preabbr`, `prfabbr`, `landarea`, `geom` | EPSG:3347 |

- Full-detail geometry (CD shapefile is 278 MB uncompressed); simplify a copy for display
- **4 of 293 CD geometries are invalid** (`ST_IsValid = false`): silver applies `ST_MakeValid`
- Cartographic files follow the shoreline, so detections over water fall outside all CDs

## Table 98-10-0007-01: Population and dwelling counts, Canada and census divisions

- 307 rows: Canada (1) + provinces and territories (13) + census divisions (293)
- Joins to boundaries on `dguid`; all 293 CDs match
- Sum of CD `population_2021` = **36,991,981**, equal to the Canada total
- Columns renamed from `Population and dwelling counts (13): <name> [n]` to snake case,
  e.g. `population_2021`, `population_2016`, `total_private_dwellings_2021`,
  `land_area_in_square_kilometres_2021`, `population_density_per_square_kilometre_2021`
- Loaded as text; typed in silver. `symbols` is `...` (not applicable) on Canada/PR rows
