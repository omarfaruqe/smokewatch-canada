-- Expected results for transform/ci/fixtures.sql, worked out by hand. dbt tests prove shape
-- (keys, ranges, relationships) but pass on empty tables; these prove the logic produced the
-- right rows. Any mismatch raises an error and fails CI.
DO $$
DECLARE
    n bigint; v numeric; d record;
BEGIN
    -- 4 unique hotspots (uid 1001 is in both layers), minus the New York one.
    SELECT count(*) INTO n FROM marts.fct_hotspots;
    IF n <> 3 THEN RAISE EXCEPTION 'fct_hotspots: expected 3 Canadian hotspots, got %', n; END IF;

    SELECT count(*) INTO n FROM marts.fct_hotspots WHERE cduid = '2466';
    IF n <> 2 THEN RAISE EXCEPTION 'fct_hotspots: expected 2 in Montreal (2466), got %', n; END IF;

    -- The fire grew between two snapshots: two versions, only the second current.
    SELECT count(*) INTO n FROM marts.dim_fire_perimeter_history WHERE perimeter_id = 'm3_polygons_current.9001';
    IF n <> 2 THEN RAISE EXCEPTION 'SCD2: expected 2 versions, got %', n; END IF;
    SELECT count(*) INTO n FROM marts.dim_fire_perimeter_history
     WHERE perimeter_id = 'm3_polygons_current.9001' AND is_current AND version = 2 AND valid_to IS NULL;
    IF n <> 1 THEN RAISE EXCEPTION 'SCD2: version 2 should be the only current version'; END IF;

    -- NAPS: 50103 padded to 050103; method 170 (all -999) ignored; AQHI from PM2.5 150,
    -- O3 40, NO2 20 = (10/10.4)*100*((e^0.01742-1)+(e^0.02148-1)+(e^0.07305-1)) ~ 11.06.
    SELECT max(aqhi) INTO v FROM staging.int_naps_aqhi_hourly WHERE naps_id = '050103';
    IF v IS NULL OR v NOT BETWEEN 10.9 AND 11.2 THEN
        RAISE EXCEPTION 'NAPS AQHI: expected ~11.06, got %', v;
    END IF;
    -- Local standard time hour-ending 01:00 at UTC-5 is 06:00 UTC.
    SELECT min(observed_at) INTO d FROM staging.int_naps_station_hourly WHERE naps_id = '050103';
    IF d.min <> '2026-06-07 06:00:00+00'::timestamptz THEN
        RAISE EXCEPTION 'NAPS UTC conversion: expected first hour 06:00 UTC, got %', d.min;
    END IF;

    -- Exposure on the smoke day: whole-division count 1000 (only Montreal has a high-risk
    -- location); nearest-station 1500 (Laval areas are within 50 km of Montreal stations).
    SELECT sum(population_exposed_high_risk) INTO n FROM marts.fct_daily_exposure WHERE day = '2026-06-07';
    IF n <> 1000 THEN RAISE EXCEPTION 'whole-division exposure: expected 1000, got %', n; END IF;
    SELECT sum(population_exposed_high_risk_da) INTO n FROM marts.fct_daily_exposure WHERE day = '2026-06-07';
    IF n <> 1500 THEN RAISE EXCEPTION 'nearest-station exposure: expected 1500, got %', n; END IF;

    -- Who is exposed (all five areas exposed): 65+ 100+80+50+40 = 270, 0-4 30+20+15+10 = 75,
    -- Indigenous identity 20+0 (suppressed)+10+5 = 35.
    SELECT sum(seniors_exposed_high_risk_da) INTO n FROM marts.fct_daily_exposure WHERE day = '2026-06-07';
    IF n <> 270 THEN RAISE EXCEPTION 'seniors exposed: expected 270, got %', n; END IF;
    SELECT sum(children_exposed_high_risk_da) INTO n FROM marts.fct_daily_exposure WHERE day = '2026-06-07';
    IF n <> 75 THEN RAISE EXCEPTION 'children exposed: expected 75, got %', n; END IF;
    SELECT sum(indigenous_exposed_high_risk_da) INTO n FROM marts.fct_daily_exposure WHERE day = '2026-06-07';
    IF n <> 35 THEN RAISE EXCEPTION 'Indigenous identity exposed: expected 35, got %', n; END IF;

    -- First Nations: Kahnawake and Kanesatake are in range and high risk; the BC band has
    -- no AQHI location within 50 km, so no row.
    SELECT count(*) INTO n FROM marts.fct_first_nation_daily_exposure
    WHERE day = '2026-06-07' AND high_risk;
    IF n <> 2 THEN RAISE EXCEPTION 'First Nations high risk: expected 2, got %', n; END IF;
    SELECT count(*) INTO n FROM marts.fct_first_nation_daily_exposure WHERE band_number = 604;
    IF n <> 0 THEN RAISE EXCEPTION 'First Nations: BC band should have no rows, got %', n; END IF;
    SELECT count(*) INTO n FROM marts.fct_first_nation_daily_exposure
    WHERE band_number = 69 AND cduid = '2466';
    IF n < 1 THEN RAISE EXCEPTION 'First Nations: Kanesatake should map to Montreal (2466)'; END IF;

    -- Weather smoke reports (15:00-20:00 UTC) land in Laval.
    SELECT smoke_report_hours INTO n FROM marts.fct_daily_exposure WHERE day = '2026-06-07' AND cduid = '2465';
    IF n <> 6 THEN RAISE EXCEPTION 'smoke reports: expected 6 hours in Laval, got %', n; END IF;

    -- Pipeline health: load history from raw._load_log, freshness from the marts.
    SELECT count(*) INTO n FROM marts.fct_pipeline_health;
    IF n <> 7 THEN RAISE EXCEPTION 'pipeline health: expected 7 datasets, got %', n; END IF;
    SELECT partitions_loaded INTO n FROM marts.fct_pipeline_health WHERE dataset = 'hotspots';
    IF n <> 2 THEN RAISE EXCEPTION 'pipeline health: expected 2 hotspot partitions, got %', n; END IF;
    SELECT data_through INTO d FROM marts.fct_pipeline_health WHERE dataset = 'hotspots';
    IF d.data_through <> '2026-06-07 20:00:00+00'::timestamptz THEN
        RAISE EXCEPTION 'pipeline health: hotspots data_through should be 20:00 UTC, got %', d.data_through;
    END IF;
    SELECT newest_partition_year INTO n FROM marts.fct_pipeline_health WHERE dataset = 'naps_hourly';
    IF n <> 2026 THEN RAISE EXCEPTION 'pipeline health: NAPS newest year should be 2026, got %', n; END IF;

    -- Forecast skill: 16:00 forecast 9 vs observed 9.2 (amendment) at 5 h lead = hit;
    -- 20:00 forecast 8 vs observed 4.0 at 9 h lead = false alarm, error +4.
    SELECT count(*) INTO n FROM marts.fct_aqhi_forecast_pairs;
    IF n <> 2 THEN RAISE EXCEPTION 'forecast pairs: expected 2, got %', n; END IF;
    SELECT mae INTO v FROM marts.fct_aqhi_forecast_skill WHERE lead_bucket = '00-06h';
    IF v <> 0.2 THEN RAISE EXCEPTION 'forecast skill 00-06h: expected MAE 0.2, got %', v; END IF;
    SELECT pod INTO v FROM marts.fct_aqhi_forecast_skill WHERE lead_bucket = '00-06h';
    IF v <> 1 THEN RAISE EXCEPTION 'forecast skill 00-06h: expected POD 1, got %', v; END IF;
    SELECT bias INTO v FROM marts.fct_aqhi_forecast_skill WHERE lead_bucket = '06-12h';
    IF v <> 4 THEN RAISE EXCEPTION 'forecast skill 06-12h: expected bias +4, got %', v; END IF;
    SELECT far INTO v FROM marts.fct_aqhi_forecast_skill WHERE lead_bucket = '06-12h';
    IF v <> 1 THEN RAISE EXCEPTION 'forecast skill 06-12h: expected FAR 1, got %', v; END IF;

    RAISE NOTICE 'all fixture expectations met';
END $$;
