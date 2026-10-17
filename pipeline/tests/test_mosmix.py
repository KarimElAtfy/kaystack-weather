from datetime import UTC, date, datetime

import pytest
from conftest import fixture, replaying
from tables import compact_on_time, read_table

from meteo import mosmix
from meteo.store import raw_name

LISTING = f"{mosmix.BASE}/16076/kml/"


def test_the_listing_names_every_issue():
    http, _ = replaying({("GET", LISTING): (200, fixture("mosmix/listing-16076.html"), {})})
    issues = mosmix.issues(http, 16076)
    assert len(issues) == 8
    assert {i.hour for i in issues} == {3, 9, 15, 21}
    assert issues == sorted(issues)


def test_only_missing_issues_are_downloaded(lake):
    routes = {("GET", LISTING): (200, fixture("mosmix/listing-16076.html"), {})}
    http, _ = replaying(routes)
    issues = mosmix.issues(http, 16076)
    for issue in issues[:-1]:
        lake.put_new("raw", raw_name("mosmix", issue, "16076", "kmz"), b"", "application/zip")
    newest_url = f"{mosmix.BASE}/16076/kml/MOSMIX_L_{issues[-1]:%Y%m%d%H}_16076.kmz"
    routes[("GET", newest_url)] = (200, fixture("mosmix/MOSMIX_L_LATEST_16076.kmz"), {})
    http, replay = replaying(routes)

    newest = {}
    mosmix.collect(lake, http, [16076], 1e12, newest)
    assert [r.url for r in replay.sent] == [LISTING, newest_url]
    assert newest == {"16076": issues[-1]}


def test_mosmix_table_converts_units(lake, all_towns):
    issue = datetime(2026, 10, 16, 9, 0, tzinfo=UTC)
    kmz = fixture("mosmix/MOSMIX_L_LATEST_16076.kmz")
    lake.put_new("raw", raw_name("mosmix", issue, "16076", "kmz"), kmz, "application/zip")
    compact_on_time(lake, all_towns, date(2026, 10, 16))

    rows = read_table(lake, "mosmix", date(2026, 10, 16))
    assert len(rows) == 247
    first = rows[0]
    assert first["wmo"] == 16076
    assert first["valid"] == "2026-10-16T10:00:00Z"
    assert first["lead_h"] == 1
    # PPPP 102320.00 Pa in the file.
    assert first["pppp_hpa"] == pytest.approx(1023.2)
    assert 0 < first["t_c"] < 30
