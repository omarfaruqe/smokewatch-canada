"""SQL behind each API endpoint. Every query reads the dbt `marts` schema only."""

from datetime import date

from sqlalchemy import Connection, text

PROVINCES = ("NL", "PE", "NS", "NB", "QC", "ON", "MB", "SK", "AB", "BC", "YT", "NT", "NU")


def _rows(conn: Connection, sql: str, **params) -> list[dict]:
    return [dict(r._mapping) for r in conn.execute(text(sql), params)]


def _feature_collection(conn: Connection, sql: str, **params) -> dict:
    """Wrap a query returning (geometry_json, properties_json) rows as GeoJSON."""
    wrapped = f"""
        select coalesce(json_build_object(
            'type', 'FeatureCollection',
            'features', json_agg(json_build_object(
                'type', 'Feature', 'geometry', q.geometry::json, 'properties', q.properties))
        ), '{{"type":"FeatureCollection","features":[]}}'::json) as fc
        from ({sql}) q
    """
    fc = conn.execute(text(wrapped), params).scalar_one()
    if fc.get("features") is None:
        fc["features"] = []
    return fc


def coverage(conn: Connection) -> dict:
    return _rows(conn, """
        select
            (select min(detected_date_utc) from marts.fct_hotspots)       as hotspots_from,
            (select max(detected_date_utc) from marts.fct_hotspots)       as hotspots_to,
            (select min(observed_date_utc) from marts.fct_aqhi_hourly)    as aqhi_from,
            (select max(observed_date_utc) from marts.fct_aqhi_hourly)    as aqhi_to,
            (select count(*) from marts.fct_hotspots)                     as hotspots,
            (select count(*) from marts.dim_census_division)              as census_divisions
    """)[0]


def national_daily(conn: Connection, start: date, end: date) -> list[dict]:
    return _rows(conn, """
        select
            day,
            sum(population_exposed_high_risk)::bigint as population_exposed_high_risk,
            sum(population_exposed_high_risk_da)::bigint as population_exposed_high_risk_da,
            sum(population_aqhi_covered_da)::bigint as population_aqhi_covered_da,
            sum(hotspot_count)::bigint                                  as hotspots,
            max(max_aqhi)                                               as peak_aqhi,
            count(*) filter (where population_exposed_high_risk > 0)    as divisions_exposed,
            coalesce(array_agg(distinct province_code order by province_code)
                filter (where population_exposed_high_risk > 0), '{}')  as provinces_exposed
        from marts.fct_daily_exposure
        where day between :start and :end
        group by day
        order by day
    """, start=start, end=end)


def division_exposure(conn: Connection, day: date, province: str | None) -> list[dict]:
    return _rows(conn, """
        select
            e.cduid, e.cd_name, e.province_code, d.province_name_en, d.province_name_fr,
            e.population_2021, e.hotspot_count, e.total_frp_mw, e.aqhi_coverage, e.max_aqhi,
            e.mean_aqhi, e.high_risk_hours, e.pm25_max_station_daily_mean, e.pm25_over_standard,
            e.smoke_report_hours, e.population_exposed_high_risk,
            e.population_exposed_high_risk_da, e.population_aqhi_covered_da
        from marts.fct_daily_exposure e
        join marts.dim_census_division d using (cduid)
        where e.day = :day and (cast(:province as text) is null or e.province_code = :province)
        order by e.population_exposed_high_risk desc, e.max_aqhi desc nulls last
    """, day=day, province=province)


def division_geojson(conn: Connection, day: date) -> dict:
    return _feature_collection(conn, """
        select
            ST_AsGeoJSON(d.geom_4326, 4) as geometry,
            json_build_object(
                'cduid', d.cduid, 'name', d.cd_name, 'province', d.province_code,
                'province_name_en', d.province_name_en, 'province_name_fr', d.province_name_fr,
                'population', d.population_2021, 'hotspots', coalesce(e.hotspot_count, 0),
                'max_aqhi', e.max_aqhi, 'high_risk_hours', coalesce(e.high_risk_hours, 0),
                'aqhi_coverage', coalesce(e.aqhi_coverage, false),
                'pm25', e.pm25_max_station_daily_mean,
                'exposed', coalesce(e.population_exposed_high_risk, 0),
                'exposed_da', coalesce(e.population_exposed_high_risk_da, 0),
                'covered_da', coalesce(e.population_aqhi_covered_da, 0)
            ) as properties
        from marts.dim_census_division d
        left join marts.fct_daily_exposure e on e.cduid = d.cduid and e.day = :day
    """, day=day)


def hotspots_geojson(conn: Connection, day: date, province: str | None, limit: int) -> dict:
    return _feature_collection(conn, """
        select
            ST_AsGeoJSON(geom, 4) as geometry,
            json_build_object(
                'id', hotspot_id, 'detected_at', detected_at, 'province', province_code,
                'cduid', cduid, 'frp_mw', frp_mw, 'fwi', fwi, 'sensor', sensor
            ) as properties
        from marts.fct_hotspots
        where detected_date_utc = :day
          and (cast(:province as text) is null or province_code = :province)
        order by frp_mw desc nulls last
        limit :limit
    """, day=day, province=province, limit=limit)


def season_perimeters_geojson(conn: Connection, year: int, province: str | None) -> dict:
    return _feature_collection(conn, """
        select
            ST_AsGeoJSON(geom_4326, 4) as geometry,
            json_build_object(
                'uid', perimeter_uid, 'province', province_code, 'cduid', cduid,
                'area_ha', round(area_ha), 'hotspots', hotspot_count,
                'first_detected_at', first_detected_at, 'last_detected_at', last_detected_at,
                'active_days', active_days
            ) as properties
        from marts.fct_fire_season_perimeters
        where season_year = :year
          and (cast(:province as text) is null or province_code = :province)
    """, year=year, province=province)


def fire_history(conn: Connection, perimeter_id: str) -> list[dict]:
    return _rows(conn, """
        select perimeter_id, version, valid_from, valid_to, is_current, cduid, province_code,
               hotspot_count, first_detected_at, last_detected_at, area_ha
        from marts.dim_fire_perimeter_history
        where perimeter_id = :pid
        order by version
    """, pid=perimeter_id)


def aqhi_hourly(conn: Connection, day: date, cduid: str) -> list[dict]:
    return _rows(conn, """
        select aqhi_source, location_id, location_name_en, location_name_fr, observed_at,
               aqhi, risk_category
        from marts.fct_aqhi_hourly
        where observed_date_utc = :day and cduid = :cduid
        order by location_id, observed_at
    """, day=day, cduid=cduid)
