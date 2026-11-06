-- Minimal raw-layer fixture for CI: every raw source dbt reads, two Montreal-area census
-- divisions (2466 Montreal, 2465 Laval), one high-risk smoke day (2026-06-07 UTC).
-- Values are chosen so every dbt data test can pass and every model produces rows.
CREATE EXTENSION IF NOT EXISTS postgis;
DROP SCHEMA IF EXISTS raw CASCADE;
CREATE SCHEMA raw;

-- ---- StatCan: boundaries (EPSG:3347), population, dissemination blocks -------------------
CREATE TABLE raw.statcan_census_divisions AS
SELECT * FROM (VALUES
    ('2466', '2021A00032466', 'Montréal', 'TÉ', '24', 499.0,
     ST_Multi(ST_Transform(ST_MakeEnvelope(-74.0, 45.40, -73.45, 45.70, 4326), 3347))),
    ('2465', '2021A00032465', 'Laval', 'TÉ', '24', 246.0,
     ST_Multi(ST_Transform(ST_MakeEnvelope(-74.0, 45.70, -73.45, 45.90, 4326), 3347)))
) AS t(cduid, dguid, cdname, cdtype, pruid, landarea, geom);

CREATE TABLE raw.statcan_provinces AS
SELECT '24'::text AS pruid, '2021A000224'::text AS dguid, 'Quebec / Québec'::text AS prname,
       'Quebec'::text AS prename, 'Québec'::text AS prfname, 'Que.'::text AS preabbr,
       'Qc'::text AS prfabbr, 1365128.0 AS landarea,
       ST_Multi(ST_Transform(ST_MakeEnvelope(-74.0, 45.40, -73.45, 45.90, 4326), 3347)) AS geom;

CREATE TABLE raw.statcan_population_cd (
    ref_date text, geo text, dguid text, population_2021 text, population_2016 text,
    population_density_per_square_kilometre_2021 text
);
INSERT INTO raw.statcan_population_cd VALUES
    ('2021', 'Canada',   '2021A000011124', '1500', '1450', '4.2'),
    ('2021', 'Quebec',   '2021A000224',    '1500', '1450', '6.0'),
    ('2021', 'Montréal', '2021A00032466',  '1000', '980',  '2.0'),
    ('2021', 'Laval',    '2021A00032465',  '500',  '470',  '2.0');

CREATE TABLE raw.statcan_geo_attributes (
    pruid text, cduid text, dauid text, da_rp_x text, da_rp_y text, da_rp_lat text,
    da_rp_lon text, dbuid text, db_pop_2021 text
);
INSERT INTO raw.statcan_geo_attributes
SELECT '24', cduid, dauid,
       ST_X(ST_Transform(ST_SetSRID(ST_MakePoint(lon, lat), 4326), 3347))::text,
       ST_Y(ST_Transform(ST_SetSRID(ST_MakePoint(lon, lat), 4326), 3347))::text,
       lat::text, lon::text, dbuid, pop
FROM (VALUES
    ('2466', '24660001', -73.60, 45.50, '24660001001', '400'),
    ('2466', '24660001', -73.60, 45.50, '24660001002', '200'),
    ('2466', '24660002', -73.70, 45.60, '24660002001', '400'),
    ('2465', '24650001', -73.75, 45.80, '24650001001', '300'),
    ('2465', '24650002', -73.65, 45.85, '24650002001', '200')
) AS d(cduid, dauid, lon, lat, dbuid, pop);

-- ---- Generic raw feature tables (as created by smokewatch.loaders.bronze_features) -------
CREATE TABLE raw._load_log (
    dataset text NOT NULL, partition text NOT NULL, sha256 text NOT NULL,
    row_count integer NOT NULL, loaded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset, partition)
);

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['cwfis_hotspots', 'cwfis_fire_perimeters', 'eccc_aqhi_observations',
                             'eccc_aqhi_forecasts', 'eccc_climate_hourly'] LOOP
        EXECUTE format('CREATE TABLE raw.%I (partition text NOT NULL, feature_id text,
            properties jsonb NOT NULL, geom geometry(Geometry, 4326),
            loaded_at timestamptz NOT NULL DEFAULT now())', t);
    END LOOP;
END $$;

-- Hotspots: two in Montreal, one in Laval, one in New York State (must be filtered out).
-- uid 1001 appears in both layers: staging must keep one row.
INSERT INTO raw.cwfis_hotspots (partition, feature_id, properties, geom) VALUES
    ('cwfis/hotspots/hotspots_24h/date=2026-06-07', 'hotspots_24h.1',
     '{"uid": 1001, "rep_date": "2026-06-07T18:00:00Z", "agency": "QC", "source": "NASA_w", "sensor": "VIIRS-I", "satellite": "NOAA-20", "frp": 12.5, "estarea": 20.1, "fwi": 27.8, "isi": 10.8, "bui": 70.5, "ffmc": 89.2, "dmc": 60.5, "dc": 211.2, "temp": 28, "rh": 30, "ws": 20, "m3_confidence": 1}',
     ST_SetSRID(ST_MakePoint(-73.55, 45.55), 4326)),
    ('cwfis/hotspots/hotspots/date=2026-06-07', 'hotspots.1',
     '{"uid": 1001, "rep_date": "2026-06-07T18:00:00Z", "agency": "QC", "source": "NASA_w", "sensor": "VIIRS-I", "frp": 12.5, "fwi": 27.8}',
     ST_SetSRID(ST_MakePoint(-73.55, 45.55), 4326)),
    ('cwfis/hotspots/hotspots/date=2026-06-07', 'hotspots.2',
     '{"uid": 1002, "rep_date": "2026-06-07T19:30:00Z", "agency": "QC", "sensor": "MODIS", "frp": 40.0, "fwi": 30.1}',
     ST_SetSRID(ST_MakePoint(-73.62, 45.48), 4326)),
    ('cwfis/hotspots/hotspots/date=2026-06-07', 'hotspots.3',
     '{"uid": 1003, "rep_date": "2026-06-07T20:00:00Z", "agency": "QC", "sensor": "VIIRS-I", "frp": 5.0, "fwi": 22.0}',
     ST_SetSRID(ST_MakePoint(-73.80, 45.80), 4326)),
    ('cwfis/hotspots/hotspots/date=2026-06-07', 'hotspots.4',
     '{"uid": 1004, "rep_date": "2026-06-07T20:00:00Z", "agency": "NY", "sensor": "VIIRS-I", "frp": 3.0}',
     ST_SetSRID(ST_MakePoint(-74.50, 43.00), 4326));

-- Fire perimeter snapshots: the same fire grows between two days (two SCD2 versions).
INSERT INTO raw.cwfis_fire_perimeters (partition, feature_id, properties, geom) VALUES
    ('cwfis/perimeters/m3_polygons_current/date=2026-06-06', 'm3_polygons_current.9001',
     '{"hcount": 5, "firstdate": "2026-06-05T18:00:00Z", "lastdate": "2026-06-06T18:00:00Z", "area": 120.5}',
     ST_SetSRID(ST_MakeEnvelope(-73.70, 45.50, -73.68, 45.52), 4326)),
    ('cwfis/perimeters/m3_polygons_current/date=2026-06-07', 'm3_polygons_current.9001',
     '{"hcount": 9, "firstdate": "2026-06-05T18:00:00Z", "lastdate": "2026-06-07T19:00:00Z", "area": 310.0}',
     ST_SetSRID(ST_MakeEnvelope(-73.71, 45.49, -73.67, 45.53), 4326));

-- ECCC AQHI observations: Montreal community, high risk in the afternoon; one amendment.
INSERT INTO raw.eccc_aqhi_observations (partition, feature_id, properties, geom)
SELECT 'eccc/aqhi-observations-realtime/date=2026-06-07', 'AQ_OBS-FAKEA-' || h,
       jsonb_build_object('id', 'AQ_OBS-FAKEA-' || h, 'location_id', 'FAKEA',
           'location_name_en', 'Montréal', 'location_name_fr', 'Montréal',
           'observation_datetime', format('2026-06-07T%s:00:00Z', lpad(h::text, 2, '0')),
           'aqhi', CASE WHEN h BETWEEN 15 AND 18 THEN 9.2 ELSE 4.0 END,
           'observation_type', CASE WHEN h = 16 THEN 'amendment' ELSE 'original' END,
           'special_notes_en', '', 'latest', h = 20),
       ST_SetSRID(ST_MakePoint(-73.58, 45.51), 4326)
FROM generate_series(10, 20) AS h;

-- ECCC AQHI forecasts: one hourly and one named-period record.
INSERT INTO raw.eccc_aqhi_forecasts (partition, feature_id, properties, geom) VALUES
    ('eccc/aqhi-forecasts-realtime/pub_date=2026-06-07', 'AQ_FCST-FAKEA-1',
     '{"aqhi_type": "AQHI-Forecast", "location_id": "FAKEA", "location_name_en": "Montréal", "publication_datetime": "2026-06-07T11:00:00Z", "forecast_datetime": "2026-06-07T20:00:00Z", "aqhi": 8, "forecast_type": "original"}',
     ST_SetSRID(ST_MakePoint(-73.58, 45.51), 4326)),
    ('eccc/aqhi-forecasts-realtime/pub_date=2026-06-07', 'AQ_FCST-FAKEA-period-1',
     '{"aqhi_type": "AQHI-Forecast-Period", "location_id": "FAKEA", "location_name_en": "Montréal", "publication_datetime": "2026-06-07T11:00:00Z", "forecast_type": "original", "forecast_period": {"period_1": {"forecast_period_en": "Today", "forecast_period_fr": "Aujourd''hui", "aqhi": 8, "aqhi_insmoke": 10}, "period_2": {"forecast_period_en": "Tonight", "forecast_period_fr": "Ce soir et cette nuit", "aqhi": 6, "aqhi_insmoke": null}}}',
     ST_SetSRID(ST_MakePoint(-73.58, 45.51), 4326));

-- ECCC hourly weather: a Laval station reporting smoke.
INSERT INTO raw.eccc_climate_hourly (partition, feature_id, properties, geom)
SELECT 'eccc/climate-hourly/date=2026-06-07', '7024000.2026.6.7.' || h,
       jsonb_build_object('ID', '7024000.2026.6.7.' || h, 'CLIMATE_IDENTIFIER', '7024000',
           'STATION_NAME', 'LAVAL TEST', 'PROVINCE_CODE', 'QC',
           'UTC_DATE', format('2026-06-07T%s:00:00', lpad(h::text, 2, '0')),
           'TEMP', 27.5, 'RELATIVE_HUMIDITY', 35, 'WIND_SPEED', 15, 'WIND_DIRECTION', 23,
           'VISIBILITY', 4, 'PRECIP_AMOUNT', 0,
           'WEATHER_ENG_DESC', CASE WHEN h >= 15 THEN 'Smoke' ELSE 'NA' END),
       ST_SetSRID(ST_MakePoint(-73.75, 45.80), 4326)
FROM generate_series(12, 20) AS h;

-- ---- NAPS: one Montreal station with PM2.5 (two co-located methods), O3 and NO2 ----------
CREATE TABLE raw.naps_stations (
    naps_id text, station_name text, city text, province_territory_en text,
    timezone_utc text, latitude text, longitude text
);
INSERT INTO raw.naps_stations VALUES
    ('050103', 'MONTRÉAL TEST', 'Montréal', 'QUEBEC', '-5', '45.6', '-73.55');

CREATE TABLE raw.naps_hourly (
    partition text NOT NULL, pollutant text, method_code text, naps_id text, city text,
    province text, latitude text, longitude text, date text,
    h01 text, h02 text, h03 text, h04 text, h05 text, h06 text, h07 text, h08 text,
    h09 text, h10 text, h11 text, h12 text, h13 text, h14 text, h15 text, h16 text,
    h17 text, h18 text, h19 text, h20 text, h21 text, h22 text, h23 text, h24 text,
    loaded_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO raw.naps_hourly
SELECT format('naps/hourly/%s/year=2026', p), pol, m, '50103', 'Montréal', 'QC', '45.6', '-73.55',
       '2026-06-07', VARIADIC_HOURS.*
FROM (VALUES ('PM25', 'PM2.5', '184', '150'), ('PM25', 'PM2.5', '170', '-999'),
             ('O3', 'O3', NULL, '40'), ('NO2', 'NO2', NULL, '20')) AS v(p, pol, m, val)
CROSS JOIN LATERAL (SELECT val, val, val, val, val, val, val, val, val, val, val, val,
                           val, val, val, val, val, val, val, val, val, val, val, val
                   ) AS VARIADIC_HOURS;

-- ---- CWFIS season perimeters archive (EPSG:3978) ------------------------------------------
CREATE TABLE raw.cwfis_season_perimeters AS
SELECT 2025 AS season_year, 555001::bigint AS uid, 120::bigint AS hcount,
       '2025/06/02 16:24:00.000'::text AS firstdate, '2025/06/26 17:13:00.000'::text AS lastdate,
       8000.5::double precision AS area, 47303.0::double precision AS consis_id,
       ST_Transform(ST_MakeEnvelope(-73.90, 45.75, -73.85, 45.80, 4326), 3978) AS geom;
