import gzip
import json
from datetime import UTC, date, datetime, timedelta

from conftest import fixture, replaying

from meteo import openmeteo
from meteo.store import FolderStore, raw_name
from scripts import backfill_runs

ARCHIVED = "open-meteo/2026/10/17/20261017T000000Z-gfs_global.json.gz"
# As the live job wrote them, when it fetched the run at 11:47.
METADATA = {
    "run_init": "2026-10-17T00:00:00+00:00",
    "run_available": "2026-10-17T06:25:43+00:00",
    "fetched_at": "2026-10-17T11:47:08+00:00",
    "points": "torre-boldone,lime,ispra-jrc,varano-borghi",
}


def archive(lake) -> None:
    body = gzip.compress(fixture("open-meteo/archived-gfs_global-2026-10-17T00.json"))
    lake.put_new("raw", ARCHIVED, body, "application/gzip", METADATA)


def test_runs_follow_the_update_interval_from_00z():
    runs = backfill_runs.runs_of(date(2026, 10, 24), date(2026, 10, 24), timedelta(hours=6))
    assert [f"{r:%H}" for r in runs] == ["00", "06", "12", "18"]
    assert runs[0] == datetime(2026, 10, 24, tzinfo=UTC)


def test_the_gfs_00z_of_17_10_holds_another_run(lake, all_towns):
    archive(lake)
    single = fixture("open-meteo/single-runs-gfs_global-2026-10-17T00-t2m.json")
    http, _ = replaying({("GET", openmeteo.SINGLE_RUNS): (200, single, {})})
    point = next(p for t in all_towns for p in t.forecast_points() if p.id == "torre-boldone")
    assert backfill_runs.mislabelled(lake, http, point, ARCHIVED)


def test_a_run_that_matches_single_runs_is_left_alone(lake, all_towns):
    archive(lake)
    block = json.loads(fixture("open-meteo/archived-gfs_global-2026-10-17T00.json"))[0]["hourly"]
    same = {"hourly": {"time": block["time"], "temperature_2m": block["temperature_2m"]}}
    http, _ = replaying({("GET", openmeteo.SINGLE_RUNS): (200, json.dumps(same).encode(), {})})
    point = next(p for t in all_towns for p in t.forecast_points() if p.id == "torre-boldone")
    assert not backfill_runs.mislabelled(lake, http, point, ARCHIVED)


def test_an_upload_writes_each_file_once_with_its_metadata(lake, tmp_path):
    folder = FolderStore(tmp_path / "folder")
    run = datetime(2026, 10, 24, 12, tzinfo=UTC)
    name = raw_name("open-meteo", run, "gfs_global", "json.gz")
    folder.put_new("raw", name, b"run", "application/gzip", {"run_init": run.isoformat()})
    folder.put_new("raw", openmeteo.missing_name(run, "meteofrance_arome_france_hd"), b"{}", "")
    backfill_runs.upload(folder, lake)
    backfill_runs.upload(folder, lake)
    assert lake.read("raw", name) == (b"run", {"run_init": run.isoformat()})
    assert len(lake.names("raw", "open-meteo/")) == 2
