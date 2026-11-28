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


def test_read_profile_csv_keeps_wanted_characteristics_and_flags():
    from smokewatch.loaders.statcan_census import read_profile_csv

    head = ("DATAFLOW,FREQ,TIME_PERIOD,REF_AREA,GENDER,CHARACTERISTIC,STATISTIC,OBS_VALUE,"
            "DECIMALS,FLAG,TOPIC,NOTE,RELEASE_DATE,GEO_LEVEL,ALT_GEO_CODE")
    rows = [
        "STC_CP:DF_DA(1.3),A5,2021,2021S051210010174,1,10,1,35,0,,2,1,2022-04-27,13,10010174",
        "STC_CP:DF_DA(1.3),A5,2021,2021S051210010174,1,1389,1,,0,6,9,1,2022-09-21,13,10010174",
        "STC_CP:DF_DA(1.3),A5,2021,2021S051210010174,1,999,1,5,0,,2,1,2022-04-27,13,10010174",
        "STC_CP:DF_DA(1.3),A5,2021,2021S051210010175,2,24,1,9,0,,2,1,2022-04-27,13,10010175",
    ]
    data = ("﻿" + "\n".join([head, *rows]) + "\n").encode()
    assert list(read_profile_csv(data)) == [
        ("10010174", "10", "35", ""),
        ("10010174", "1389", "", "6"),
    ]


def test_read_first_nations_handles_bom_and_quoted_names():
    import io
    import zipfile

    from smokewatch.loaders.statcan_census import read_first_nations

    csv_text = ("﻿BAND_NUMBER,BAND_NAME,LONGITUDE,LATITUDE,COORD_SYS\n"
                '604,?Akisq\'nuk First Nation,-115.96,50.45,GCS\n'
                '123,"Nation, with comma",-108.2,53.1,GCS\n')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Premiere_Nation_First_Nation.csv", csv_text.encode())
    assert list(read_first_nations(buf.getvalue())) == [
        ("604", "?Akisq'nuk First Nation", "-115.96", "50.45"),
        ("123", "Nation, with comma", "-108.2", "53.1"),
    ]
