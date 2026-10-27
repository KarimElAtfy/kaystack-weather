import gzip
import json
from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import fixture, replaying
from tables import compact_on_time, read_table, table_types

from meteo import openmeteo, towns
from meteo.store import raw_name

META_D2 = "https://api.open-meteo.com/data/dwd_icon_d2/static/meta.json"
META_CH1_ENS = (
    "https://ensemble-api.open-meteo.com/data/meteoswiss_icon_ch1_ensemble/static/meta.json"
)
RUN_D2 = datetime(2026, 10, 16, 9, 0, tzinfo=UTC)


SINGLE_D2 = fixture("open-meteo/single-runs-icon_d2-2026-10-27T06.json")
MISSING = fixture("open-meteo/single-runs-missing-arome-2026-10-24T06.json")
THREE_HOURS = timedelta(hours=3)


@pytest.fixture(autouse=True)
def one_model_each(monkeypatch):
    monkeypatch.setattr(openmeteo, "_meta", {})
    monkeypatch.setitem(openmeteo.KINDS, "nwp", (openmeteo.HOST, {"icon_d2": "dwd_icon_d2"}, ""))
    one_ensemble = {"meteoswiss_icon_ch1_ensemble": "meteoswiss_icon_ch1_ensemble"}
    monkeypatch.setitem(
        openmeteo.KINDS, "ensemble", (openmeteo.ENSEMBLE_HOST, one_ensemble, "ens-")
    )


def run_slot(hours_back: int) -> datetime:
    """A three-hourly run start, so many hours before the last one."""
    now = datetime.now(UTC)
    slot = now.replace(hour=now.hour // 3 * 3, minute=0, second=0, microsecond=0)
    return slot - timedelta(hours=hours_back)


def stamp(run: datetime) -> str:
    return f"{run:%Y-%m-%dT%H:%M}"


def meta_d2(latest: datetime, available: datetime):
    """The recorded meta.json of ICON-D2, moved to the given run."""
    body = json.loads(fixture("open-meteo/meta-dwd_icon_d2.json"))
    body["last_run_initialisation_time"] = int(latest.timestamp())
    body["last_run_availability_time"] = int(available.timestamp())
    return (200, json.dumps(body).encode(), {})


def single_runs(missing=()):
    def answer(request):
        run = parse_qs(urlsplit(request.url).query)["run"][0]
        return (400, MISSING, {}) if run in missing else (200, SINGLE_D2, {})

    return answer


def archive(lake, run_init: datetime) -> None:
    name = raw_name("open-meteo", run_init, "icon_d2", "json.gz")
    lake.put_new("raw", name, gzip.compress(SINGLE_D2), "application/gzip", {})


def asked(replay) -> list[str]:
    return [
        parse_qs(urlsplit(r.url).query)["run"][0]
        for r in replay.sent
        if r.url.startswith(openmeteo.SINGLE_RUNS)
    ]


def collect(lake, all_towns, http, kind="nwp"):
    newest = {}
    openmeteo.collect_runs(lake, http, towns.forecast_points(all_towns), kind, 1e12, newest)
    return newest


def d2_routes(latest, available, missing=()):
    return {
        ("GET", META_D2): meta_d2(latest, available),
        ("GET", openmeteo.SINGLE_RUNS): single_runs(missing),
    }


def test_every_run_since_the_last_archived_is_asked_by_its_start(lake, all_towns):
    latest = run_slot(3)
    archive(lake, latest - 2 * THREE_HOURS)
    http, replay = replaying(d2_routes(latest, latest + timedelta(hours=1, minutes=30)))
    newest = collect(lake, all_towns, http)

    assert asked(replay) == [stamp(latest - THREE_HOURS), stamp(latest)]
    assert newest == {"icon_d2": latest}
    raw, metadata = lake.read("raw", raw_name("open-meteo", latest, "icon_d2", "json.gz"))
    assert gzip.decompress(raw) == SINGLE_D2
    assert metadata["run_init"] == latest.isoformat()
    assert "run=" in metadata["request"] and "past_hours" not in metadata["request"]
    assert "elevation=311%2C238%2C249%2C241" in metadata["request"]
    # meta.json gives the availability of its newest run alone.
    _, earlier = lake.read(
        "raw", raw_name("open-meteo", latest - THREE_HOURS, "icon_d2", "json.gz")
    )
    assert "run_available" in metadata and "run_available" not in earlier


def test_the_newest_run_waits_ten_minutes_but_the_one_before_does_not(lake, all_towns):
    latest = run_slot(0)
    archive(lake, latest - 2 * THREE_HOURS)
    http, replay = replaying(d2_routes(latest, datetime.now(UTC) - timedelta(minutes=5)))
    assert collect(lake, all_towns, http) == {"icon_d2": latest - THREE_HOURS}
    assert asked(replay) == [stamp(latest - THREE_HOURS)]


def test_a_run_open_meteo_never_had_is_marked_and_passed(lake, all_towns):
    latest = run_slot(3)
    gap = latest - THREE_HOURS
    archive(lake, latest - 2 * THREE_HOURS)
    http, replay = replaying(d2_routes(latest, latest + timedelta(hours=2), {stamp(gap)}))
    assert collect(lake, all_towns, http) == {"icon_d2": latest}
    assert lake.exists("raw", openmeteo.missing_name(gap, "icon_d2"))
    assert not lake.exists("raw", raw_name("open-meteo", gap, "icon_d2", "json.gz"))

    collect(lake, all_towns, http)
    assert len(asked(replay)) == 2


def test_a_newest_run_single_runs_lacks_yet_is_asked_again(lake, all_towns):
    latest = run_slot(3)
    archive(lake, latest - THREE_HOURS)
    http, replay = replaying(d2_routes(latest, latest + timedelta(hours=2), {stamp(latest)}))
    collect(lake, all_towns, http)
    collect(lake, all_towns, http)
    assert asked(replay) == [stamp(latest)] * 2
    assert not lake.exists("raw", openmeteo.missing_name(latest, "icon_d2"))


def test_after_an_outage_eight_runs_are_caught_up_at_a_time(lake, all_towns):
    latest = run_slot(3)
    archive(lake, latest - 10 * THREE_HOURS)
    http, replay = replaying(d2_routes(latest, latest + timedelta(hours=2)))
    collect(lake, all_towns, http)
    assert asked(replay) == [stamp(latest - k * THREE_HOURS) for k in range(7, -1, -1)]


def test_a_model_never_archived_starts_from_its_newest_run(lake, all_towns):
    latest = run_slot(3)
    http, replay = replaying(d2_routes(latest, latest + timedelta(hours=2)))
    assert collect(lake, all_towns, http) == {"icon_d2": latest}
    assert asked(replay) == [stamp(latest)]


def test_one_failing_model_does_not_stop_the_others(lake, all_towns, monkeypatch):
    models = {"icon_eu": "dwd_icon_eu", "icon_d2": "dwd_icon_d2"}
    monkeypatch.setitem(openmeteo.KINDS, "nwp", (openmeteo.HOST, models, ""))
    latest = run_slot(3)
    routes = d2_routes(latest, latest + timedelta(hours=2))
    routes[("GET", "https://api.open-meteo.com/data/dwd_icon_eu/static/meta.json")] = (
        400,
        b'{"error": true, "reason": "recorded for the test"}',
        {},
    )
    http, _ = replaying(routes)
    newest = {}
    with pytest.raises(RuntimeError, match="icon_eu"):
        openmeteo.collect_runs(lake, http, towns.forecast_points(all_towns), "nwp", 1e12, newest)
    assert list(newest) == ["icon_d2"]


def ensemble_routes(*runs: datetime):
    """meta.json of CH1-EPS answering each run in turn, before and after the fetch."""
    body = json.loads(fixture("open-meteo/meta-ens-meteoswiss_icon_ch1_ensemble.json"))
    answers = iter(runs)

    def meta_answer(request):
        run = next(answers)
        body["last_run_initialisation_time"] = int(run.timestamp())
        body["last_run_availability_time"] = int((run + timedelta(hours=2)).timestamp())
        return 200, json.dumps(body).encode(), {}

    members = fixture("open-meteo/ensemble-meteoswiss_icon_ch1_ensemble.json")
    return {("GET", META_CH1_ENS): meta_answer, ("GET", openmeteo.ENSEMBLE): (200, members, {})}


def test_an_ensemble_run_is_kept_while_meta_json_shows_it(lake, all_towns):
    run = run_slot(3)
    http, _ = replaying(ensemble_routes(run, run))
    assert collect(lake, all_towns, http, "ensemble") == {"meteoswiss_icon_ch1_ensemble": run}
    name = raw_name("open-meteo", run, "ens-meteoswiss_icon_ch1_ensemble", "json.gz")
    assert lake.read("raw", name)[1]["run_init"] == run.isoformat()


def test_an_ensemble_run_that_moves_on_during_the_fetch_is_not_kept(lake, all_towns):
    run = run_slot(3)
    http, _ = replaying(ensemble_routes(run, run + THREE_HOURS))
    with pytest.raises(RuntimeError, match="meteoswiss_icon_ch1_ensemble"):
        collect(lake, all_towns, http, "ensemble")
    assert lake.names("raw", "open-meteo/") == []


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


def test_a_corrected_copy_replaces_the_run_it_follows(lake, all_towns):
    day = "open-meteo/2026/10/16/20261016T090000Z-icon_d2"
    body = gzip.compress(fixture("open-meteo/forecast-icon_d2-run.json"))
    for suffix, fetched in (
        (".json.gz", "2026-10-16T14:47:00+00:00"),
        (".v2.json.gz", "2026-10-27T17:30:00+00:00"),
    ):
        metadata = {
            "run_init": RUN_D2.isoformat(),
            "fetched_at": fetched,
            "points": "torre-boldone,lime,ispra-jrc,varano-borghi",
        }
        lake.put_new("raw", day + suffix, body, "application/gzip", metadata)
    missing = openmeteo.missing_name(RUN_D2 + timedelta(hours=3), "icon_d2")
    lake.put_new("raw", missing, b"{}", "application/json")
    compact_on_time(lake, all_towns, date(2026, 10, 16))

    nwp = read_table(lake, "nwp_hourly", date(2026, 10, 16))
    assert {r["fetched_at"] for r in nwp} == {"2026-10-27T17:30:00Z"}
    assert len(nwp) == len({(r["point"], r["valid"]) for r in nwp})
