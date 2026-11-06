"""Pure-function tests for the census loader (no database)."""

import pytest

pytest.importorskip("geopandas")

from smokewatch.loaders.statcan_census import clean_column  # noqa: E402


@pytest.mark.parametrize("raw,clean", [
    ("Population and dwelling counts (13): Population, 2021 [1]", "population_2021"),
    ("Population and dwelling counts (13): Population percentage change, 2016 to 2021 [3]",
     "population_percentage_change_2016_to_2021"),
    ("Population and dwelling counts (13): Land area in square kilometres, 2021 [10]",
     "land_area_in_square_kilometres_2021"),
    ("DGUID", "dguid"),
    ("REF_DATE", "ref_date"),
])
def test_clean_column(raw, clean):
    assert clean_column(raw) == clean


def test_read_geo_attributes_keeps_codes_and_handles_latin1():
    import io
    import zipfile

    from smokewatch.loaders.statcan_census import GEO_ATTRIBUTE_COLUMNS, read_geo_attributes

    header = ",".join(["PRNAME_PRNOM", *GEO_ATTRIBUTE_COLUMNS])
    row = ",".join(["Québec", "24", "2466", "24660001", "7629000.1", "1240000.2",
                    "45.5", "-73.6", "24660001001", "57"])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("2021_92-151_X.csv", (header + "\n" + row + "\n").encode("latin-1"))
    df = read_geo_attributes(buf.getvalue())
    assert list(df.columns) == list(GEO_ATTRIBUTE_COLUMNS.values())
    r = df.iloc[0]
    assert r["dauid"] == "24660001" and r["cduid"] == "2466" and r["db_pop_2021"] == "57"
