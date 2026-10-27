import json
from datetime import UTC, date, datetime, timedelta

import pytest
from conftest import fixture, replaying

from meteo import arpa, check, compact, openmeteo, radar
from meteo.store import raw_name

DAY = date(2026, 10, 14)
DPC = "https://radar-api.protezionecivile.it/downloadProduct"
ENV = {
    "USER_AGENT": "weather.kaystack.dev github.com/KarimElAtfy/kaystack-weather",
    "RADAR_ORIGIN": "x",
}
NOT_AT_DPC = datetime(2026, 10, 14, 3, 0, tzinfo=UTC)
AT_DPC = datetime(2026, 10, 14, 3, 5, tzinfo=UTC)


def iem_times() -> dict[str, list[str]]:
    times: dict[str, list[str]] = {}
    for line in fixture("check/iem-asos-2026-10-14.csv").decode().splitlines()[1:]:
        station, valid, _ = line.split(",", 2)
        times.setdefault(station, []).append(valid[11:16])
    return times


@pytest.fixture
def day_in_the_lake(lake):
    start = datetime(2026, 10, 14, tzinfo=UTC)
    for slot in range(288):
        frame = start + slot * radar.STEP
        if frame not in (NOT_AT_DPC, AT_DPC):
            lake.put_new("raw", raw_name("radar", frame, "sri", "u16.zlib"), b"", "x")
    counts = {
        "arpa": {"32355/4": 144, "8145/1": 144, "8161/4": 144},
        "metar": {i: {"routine": 48, "obs_times": t} for i, t in iem_times().items()},
        "nwp": dict(check.RUNS),
        "ensemble": dict(check.ENSEMBLE_RUNS),
        "mosmix": {"16076": 4, "16066": 4},
        "yr": {"torre-boldone": 4, "lime": 4, "ispra-jrc": 4, "varano-borghi": 3},
    }
    lake.put("curated", compact.completeness_name(DAY), json.dumps(counts).encode(), "")
    return lake


def sources(monkeypatch):
    def link(request):
        asked = datetime.fromtimestamp(json.loads(request.body)["productDate"] / 1000, UTC)
        if asked == AT_DPC:
            key = f"SRI/{asked:%d-%m-%Y-%H-%M}.tif"
            return 200, json.dumps({"key": key, "url": "https://s3.example/x"}).encode(), {}
        return 500, fixture("radar/downloadProduct-SRI-missing.json"), {}

    http, replay = replaying(
        {
            ("POST", DPC): link,
            ("GET", arpa.URL): (200, fixture("check/arpa-count-2026-10-14.json"), {}),
            ("GET", check.IEM): (200, fixture("check/iem-asos-2026-10-14.csv"), {}),
        }
    )
    monkeypatch.setattr(check.web, "session", lambda *args, **kwargs: http)
    return replay


def test_each_source_is_held_against_its_own_count(day_in_the_lake, all_towns, monkeypatch):
    replay = sources(monkeypatch)
    rows = {
        source: (ok, detail)
        for source, ok, detail in check.check_day(day_in_the_lake, ENV, all_towns, DAY)
    }

    # DPC still has 03:05, so the lake missed it; 03:00 is a gap DPC has too.
    assert rows["radar"] == (False, "286 of 288 stored, 1 absent at DPC; DPC has 03:05")
    assert rows["arpa"][0] is True
    assert rows["metar"] == (True, "routine {'LIMC': 48, 'LIME': 48}, IEM has 96 reports")
    assert rows["open-meteo"][0] and rows["ensemble"][0] and rows["mosmix"][0]
    assert rows["yr"] == (False, "varano-borghi 3/4")
    asked = next(r.url for r in replay.sent if r.url.startswith(arpa.URL))
    assert "data+%3E+%272026-10-14T01%3A00%3A00%27" in asked


def test_a_report_iem_has_and_the_lake_lacks_fails(day_in_the_lake, all_towns, monkeypatch):
    sources(monkeypatch)
    name = compact.completeness_name(DAY)
    counts = json.loads(day_in_the_lake.read("curated", name)[0])
    counts["metar"]["LIME"]["obs_times"].remove("12:20")
    counts["arpa"]["8145/1"] = 143
    day_in_the_lake.put("curated", name, json.dumps(counts).encode(), "")

    rows = {
        source: (ok, detail)
        for source, ok, detail in check.check_day(day_in_the_lake, ENV, all_towns, DAY)
    }
    assert rows["metar"][0] is False
    assert rows["metar"][1].endswith("lake lacks LIME 12:20")
    assert rows["arpa"] == (False, "431 values, ARPA has 432; lake/ARPA differ: 8145/1 143/144")


def test_a_day_without_compaction_fails_at_once(lake, all_towns):
    assert check.check_day(lake, ENV, all_towns, DAY + timedelta(days=1)) == [
        ("compaction", False, "no completeness/2026-10-15.json")
    ]


def test_a_run_open_meteo_never_had_is_not_owed(day_in_the_lake, all_towns, monkeypatch):
    sources(monkeypatch)
    name = compact.completeness_name(DAY)
    counts = json.loads(day_in_the_lake.read("curated", name)[0])
    # As on 24/10: AROME 00Z, 03Z and 15Z stored, the other five never published.
    counts["nwp"]["meteofrance_arome_france_hd"] = 3
    counts["ensemble"]["ecmwf_ifs025_ensemble"] = 2
    day_in_the_lake.put("curated", name, json.dumps(counts).encode(), "")
    for hour in (6, 9, 12, 18):
        run = datetime(2026, 10, 14, hour, tzinfo=UTC)
        marker = openmeteo.missing_name(run, "meteofrance_arome_france_hd")
        day_in_the_lake.put_new("raw", marker, b"{}", "application/json")

    def rows():
        return {s: (ok, d) for s, ok, d in check.check_day(day_in_the_lake, ENV, all_towns, DAY)}

    assert rows()["open-meteo"] == (
        False,
        "meteofrance_arome_france_hd 3/4; absent upstream: meteofrance_arome_france_hd 4",
    )
    run = datetime(2026, 10, 14, 21, tzinfo=UTC)
    marker = openmeteo.missing_name(run, "meteofrance_arome_france_hd")
    day_in_the_lake.put_new("raw", marker, b"{}", "application/json")
    assert rows()["open-meteo"] == (
        True,
        "73 published, all in; absent upstream: meteofrance_arome_france_hd 5",
    )
    # Open-Meteo keeps no ensemble runs, so one the lake lacks stays missing.
    assert rows()["ensemble"] == (False, "ecmwf_ifs025_ensemble 2/4")
