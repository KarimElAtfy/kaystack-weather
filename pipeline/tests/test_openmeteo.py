import gzip
import json
from datetime import UTC, date, datetime, timedelta

import pytest
from conftest import fixture, replaying
from tables import compact_on_time, read_table, table_types

from meteo import openmeteo, towns

META_D2 = "https://api.open-meteo.com/data/dwd_icon_d2/static/meta.json"
META_CH1_ENS = (
    "https://ensemble-api.open-meteo.com/data/meteoswiss_icon_ch1_ensemble/static/meta.json"
)
RUN_D2 = datetime(2026, 10, 16, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def one_model_each(monkeypatch):
    monkeypatch.setattr(openmeteo, "_meta", {})
    nwp = openmeteo.KINDS["nwp"]
    ensemble = openmeteo.KINDS["ensemble"]
    monkeypatch.setitem(openmeteo.KINDS, "nwp", (*nwp[:2], {"icon_d2": "dwd_icon_d2"}, *nwp[3:]))
    one_ensemble = {"meteoswiss_icon_ch1_ensemble": "meteoswiss_icon_ch1_ensemble"}
    monkeypatch.setitem(openmeteo.KINDS, "ensemble", (*ensemble[:2], one_ensemble, *ensemble[3:]))


def meta_answer(request):
    if request.headers.get("If-None-Match") == '"1792146384-598"':
        return 304, b"", {}
    return 200, fixture("open-meteo/meta-dwd_icon_d2.json"), {"ETag": '"1792146384-598"'}


def test_a_new_run_is_fetched_once(lake, all_towns):
    points = towns.forecast_points(all_towns)
    http, replay = replaying(
        {
            ("GET", META_D2): meta_answer,
            ("GET", openmeteo.FORECAST): (200, fixture("open-meteo/forecast-icon_d2-run.json"), {}),
        }
    )
    newest = {}
    openmeteo.collect_runs(lake, http, points, "nwp", 1e12, newest)
    openmeteo.collect_runs(lake, http, points, "nwp", 1e12, newest)

    (name,) = lake.names("raw", "open-meteo/")
    assert name == "open-meteo/2026/10/16/20261016T090000Z-icon_d2.json.gz"
    raw, metadata = lake.read("raw", name)
    assert gzip.decompress(raw) == fixture("open-meteo/forecast-icon_d2-run.json")
    assert metadata["run_init"] == RUN_D2.isoformat()
    assert metadata["points"] == "torre-boldone,lime,ispra-jrc,varano-borghi"
    assert "elevation=311%2C238%2C249%2C241" in metadata["request"]
    assert newest == {"icon_d2": RUN_D2}
    assert [r.url.split("?")[0] for r in replay.sent] == [META_D2, openmeteo.FORECAST, META_D2]
    assert replay.sent[2].headers["If-None-Match"] == '"1792146384-598"'


def test_a_run_is_left_alone_for_ten_minutes_after_it_is_available(lake, all_towns):
    now = datetime.now(UTC)
    meta = {
        "last_run_initialisation_time": int((now - timedelta(hours=2)).timestamp()),
        "last_run_availability_time": int((now - timedelta(minutes=5)).timestamp()),
    }
    http, replay = replaying({("GET", META_D2): (200, json.dumps(meta).encode(), {})})
    newest = {}
    openmeteo.collect_runs(lake, http, towns.forecast_points(all_towns), "nwp", 1e12, newest)
    assert lake.names("raw", "open-meteo/") == []
    assert newest == {}
    assert len(replay.sent) == 1


def test_one_failing_model_does_not_stop_the_others(lake, all_towns, monkeypatch):
    nwp = openmeteo.KINDS["nwp"]
    models = {"icon_eu": "dwd_icon_eu", "icon_d2": "dwd_icon_d2"}
    monkeypatch.setitem(openmeteo.KINDS, "nwp", (*nwp[:2], models, *nwp[3:]))
    http, _ = replaying(
        {
            ("GET", "https://api.open-meteo.com/data/dwd_icon_eu/static/meta.json"): (
                400,
                b'{"error": true, "reason": "recorded for the test"}',
                {},
            ),
            ("GET", META_D2): meta_answer,
            ("GET", openmeteo.FORECAST): (200, fixture("open-meteo/forecast-icon_d2-run.json"), {}),
        }
    )
    newest = {}
    with pytest.raises(RuntimeError, match="icon_eu"):
        openmeteo.collect_runs(lake, http, towns.forecast_points(all_towns), "nwp", 1e12, newest)
    assert list(newest) == ["icon_d2"]


def test_ensemble_members_include_the_control():
    raw = gzip.compress(fixture("open-meteo/ensemble-meteoswiss_icon_ch1_ensemble.json"))
    metadata = {
        "run_init": "2026-10-16T09:00:00+00:00",
        "run_available": "2026-10-16T11:00:00+00:00",
        "fetched_at": "2026-10-16T12:40:00+00:00",
        "points": "torre-boldone,lime,ispra-jrc,varano-borghi",
    }
    rows = list(openmeteo.member_rows(raw, metadata, "meteoswiss_icon_ch1_ensemble"))
    assert sorted({r["member"] for r in rows}) == list(range(11))
    assert {r["point"] for r in rows} == {"torre-boldone", "lime", "ispra-jrc", "varano-borghi"}


def test_nwp_and_ensemble_tables(lake, all_towns):
    for name, body, run_init in (
        ("20261016T090000Z-icon_d2.json.gz", "forecast-icon_d2-run.json", RUN_D2),
        (
            "20261016T090000Z-ens-meteoswiss_icon_ch1_ensemble.json.gz",
            "ensemble-meteoswiss_icon_ch1_ensemble.json",
            RUN_D2,
        ),
    ):
        metadata = {
            "run_init": run_init.isoformat(),
            "run_available": (run_init + timedelta(hours=2)).isoformat(),
            "fetched_at": (run_init + timedelta(hours=3)).isoformat(),
            "points": "torre-boldone,lime,ispra-jrc,varano-borghi",
        }
        data = gzip.compress(fixture(f"open-meteo/{body}"))
        lake.put_new("raw", f"open-meteo/2026/10/16/{name}", data, "application/gzip", metadata)
    compact_on_time(lake, all_towns, date(2026, 10, 16))

    nwp = read_table(lake, "nwp_hourly", date(2026, 10, 16))
    assert {r["point"] for r in nwp} == {"torre-boldone", "lime", "ispra-jrc", "varano-borghi"}
    assert min(r["valid"] for r in nwp) == "2026-10-16T09:00:00Z"
    assert table_types(lake, "nwp_hourly", date(2026, 10, 16))["temperature_2m"] == "FLOAT"

    hourly = read_table(lake, "ens_hourly", date(2026, 10, 16))
    assert {r["n_members"] for r in hourly} == {11}
    first = min((r for r in hourly if r["point"] == "lime"), key=lambda r: r["valid"])
    assert first["t2m_p10"] <= first["t2m_p50"] <= first["t2m_p90"]

    completeness = json.loads(lake.read("curated", "completeness/2026-10-16.json")[0])
    assert completeness["nwp"] == {"icon_d2": 1}
    assert completeness["ensemble"] == {"meteoswiss_icon_ch1_ensemble": 1}
