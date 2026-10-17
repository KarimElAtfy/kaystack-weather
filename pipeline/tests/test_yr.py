import gzip
from datetime import UTC, date, datetime

import pytest
from conftest import fixture, replaying
from tables import compact_on_time, read_table

from meteo import towns, yr
from meteo.store import raw_name

# As recorded, except Expires, moved into the past so the next run may ask again.
HEADERS = {
    "Last-Modified": "Fri, 16 Oct 2026 12:23:13 GMT",
    "Expires": "Fri, 16 Oct 2026 00:54:02 GMT",
}


@pytest.fixture(autouse=True)
def fresh_instance(monkeypatch):
    monkeypatch.setattr(yr, "_seen", {})


@pytest.mark.parametrize(
    ("degrees", "sent"),
    [(45.71899, "45.7189"), (9.71029, "9.7102"), (45.7190, "45.7190"), (45.0014, "45.0014")],
)
def test_coordinates_are_truncated_to_four_decimals(degrees, sent):
    assert yr.truncate(degrees) == sent


def test_a_forecast_is_stored_and_the_next_ask_is_conditional(lake, all_towns):
    (point,) = [p for p in towns.forecast_points(all_towns) if p.id == "torre-boldone"]
    body = fixture("yr/locationforecast-complete-torre-boldone.json")
    answers = iter([(200, body, HEADERS), (304, b"", HEADERS)])
    http, replay = replaying({("GET", yr.URL): lambda request: next(answers)})

    newest = {}
    yr.collect(lake, http, [point], 1e12, newest)
    yr.collect(lake, http, [point], 1e12, newest)

    (name,) = lake.names("raw", "yr/")
    raw, metadata = lake.read("raw", name)
    assert gzip.decompress(raw) == body
    assert metadata == {"updated_at": "2026-10-16T11:21:06+00:00"}
    assert newest == {"torre-boldone": datetime(2026, 10, 16, 11, 21, 6, tzinfo=UTC)}
    assert "lat=45.7190&lon=9.7102&altitude=311" in replay.sent[0].url
    assert "If-Modified-Since" not in replay.sent[0].headers
    assert replay.sent[1].headers["If-Modified-Since"] == HEADERS["Last-Modified"]


def test_nothing_is_asked_before_expires(lake, all_towns):
    points = towns.forecast_points(all_towns)
    future = {"Expires": "Fri, 16 Oct 2099 12:54:02 GMT"}
    body = fixture("yr/locationforecast-complete-torre-boldone.json")
    http, replay = replaying({("GET", yr.URL): (200, body, future)})
    yr.collect(lake, http, points, 1e12, {})
    yr.collect(lake, http, points, 1e12, {})
    assert len(replay.sent) == len(points)


def test_yr_table(lake, all_towns):
    fetched = datetime(2026, 10, 16, 12, 10, tzinfo=UTC)
    body = gzip.compress(fixture("yr/locationforecast-complete-torre-boldone.json"))
    lake.put_new(
        "raw", raw_name("yr", fetched, "torre-boldone", "json.gz"), body, "application/gzip"
    )
    compact_on_time(lake, all_towns, date(2026, 10, 16))

    rows = {r["valid"]: r for r in read_table(lake, "yr", date(2026, 10, 16))}
    first = rows["2026-10-16T12:00:00Z"]
    assert first["point"] == "torre-boldone"
    assert first["fetched_at"] == "2026-10-16T12:10:00Z"
    assert first["updated_at"] == "2026-10-16T11:21:06Z"
    assert first["t_c"] == pytest.approx(19.5)
    assert rows["2026-10-16T13:00:00Z"]["symbol_1h"] == "clearsky_day"
    assert rows["2026-10-16T18:00:00Z"]["tmax_6h"] == pytest.approx(19.8)
