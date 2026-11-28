# Source: Statistics Canada 2021 Census Profile, dissemination areas

- **Publisher:** Statistics Canada
- **Licence:** Statistics Canada Open Licence
- **Access:** Census Profile web data service (SDMX REST),
  `https://api.statcan.gc.ca/census-recensement/profile/sdmx/rest/data/STC_CP,DF_DA/A5..1.1+10+24+1389.1?format=csv`
  (frequency `A5`, all geographies, gender `1` = total, the four characteristics, statistic `1` = counts)
- **Bronze:** `statcan/census2021/profile/da_age_indigenous.csv` (static, sha256 manifest)
- **Raw table:** `raw.statcan_profile_da` (`dauid`, `characteristic`, `obs_value`, `flag`, all text)

The comprehensive Census Profile download page is behind a browser challenge; the pipeline
uses the official web data service instead and does not try to get around the challenge.

## Characteristics (codelist `CL_CHARACTERISTIC`)

| Code | Name | Data |
|---|---|---|
| 1 | Population, 2021 | 100% |
| 10 | 0 to 4 years | 100% |
| 24 | 65 years and over | 100% |
| 1389 | Indigenous identity | 25% sample, population in private households |

## Profile (November 2026 pull)

- 231,744 rows: 57,936 dissemination areas x 4 characteristics; one request, ~28 MB, ~75 s
- `REF_AREA` is the DGUID (`2021S0512` + DAUID); `ALT_GEO_CODE` is the DAUID
- Suppressed values have an empty `OBS_VALUE` and a `FLAG` code (e.g. `6` = suppressed for
  confidentiality); staging keeps them null and exposure counts them as zero
- Sample counts are randomly rounded, so small areas do not add up exactly
