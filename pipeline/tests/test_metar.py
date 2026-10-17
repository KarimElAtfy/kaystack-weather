import gzip
from datetime import UTC, date, datetime

import pytest
from conftest import fixture, replaying
from tables import compact_on_time, read_table

from meteo import metar
from meteo.store import raw_name


def test_reports_are_stored_with_the_newest_per_airport(lake):
    body = fixture("metar/awc-metar-sample.json")
    http, _ = replaying({("GET", metar.URL): (200, body, {})})
    newest = {}
    metar.collect(lake, http, ["LIME", "LIMC"], newest)
    (name,) = lake.names("raw", "metar/")
    assert gzip.decompress(lake.read("raw", name)[0]) == body
    assert newest == {
        "LIME": datetime(2026, 10, 16, 11, 50, tzinfo=UTC),
        "LIMC": datetime(2026, 10, 16, 11, 50, tzinfo=UTC),
    }


def test_no_report_in_three_hours_stores_nothing(lake):
    # Recorded: AWC answers 204 with an empty body.
    http, _ = replaying({("GET", metar.URL): (204, b"", {})})
    newest = {}
    metar.collect(lake, http, ["LIME"], newest)
    assert lake.names("raw", "metar/") == []
    assert newest == {}


@pytest.mark.parametrize(
    ("report", "metres"),
    [
        ("METAR LIME 161150Z VRB03KT 6000 NSC 20/14 Q1021 NOSIG", 6000),
        ("METAR LIMC 161120Z 21003KT 150V260 9999 SCT020 19/13 Q1021 NOSIG", 9999),
        ("METAR LIMC 160650Z 00000KT CAVOK 09/08 Q1024 NOSIG", 9999),
        ("METAR COR LIME 160620Z 33002KT 0300 R28/0450N FG VV001 08/08 Q1024", 300),
        ("METAR LIME 160620Z AUTO 33002KT 9999NDV NCD 08/08 Q1024", 9999),
        ("METAR LIME 160620Z 33002KT 19/14 Q1024", None),
    ],
)
def test_visibility_is_read_from_the_report(report, metres):
    assert metar.visibility_m(report) == metres


def test_reports_seen_in_several_pulls_are_kept_once(lake, all_towns):
    body = gzip.compress(fixture("metar/awc-metar-sample.json"))
    for minute in (7, 37):
        when = datetime(2026, 10, 16, 12, minute, tzinfo=UTC)
        lake.put_new("raw", raw_name("metar", when, "awc", "json.gz"), body, "application/gzip")
    compact_on_time(lake, all_towns, date(2026, 10, 16))

    rows = read_table(lake, "obs_metar", date(2026, 10, 16))
    assert len(rows) == 8
    vrb = next(r for r in rows if r["raw"].startswith("METAR LIME 161150Z VRB"))
    assert vrb["wind_dir"] is None
    assert vrb["wind_vrb"] is True
    assert vrb["qc"] == 128
    assert vrb["vis_m"] == 6000
