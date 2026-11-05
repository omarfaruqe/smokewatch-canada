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
