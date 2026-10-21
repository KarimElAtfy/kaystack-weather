import json
from datetime import UTC, date, datetime

import duckdb
import pytest
from conftest import fixture, replaying
from tables import read_table

from meteo import compact, openmeteo, towns
from scripts import backfill_openmeteo as backfill

RUN = datetime(2024, 3, 20, tzinfo=UTC)
IFS = "open-meteo/single-runs-ecmwf_ifs-2024-03-20T00.json"
D2 = "open-meteo/previous-runs-icon_d2-2024-03-16.json"
NOT_AVAILABLE = (
    b'{"reason":"The requested model run is not available. Model: ecmwf_ifs, '
    b'run: 2024-03-20T06:00Z","error":true}'
)


@pytest.fixture
def points(all_towns):
    return towns.forecast_points(all_towns)


def budget(lake, limit=5000):
    return backfill.Budget(lake.root, limit, per_minute=float("inf"))


def spent(lake):
    return json.loads((lake.root / "calls.json").read_text())[datetime.now(UTC).date().isoformat()]


def test_a_run_is_fetched_once(lake, points):
    http, replay = replaying({("GET", backfill.SINGLE): (200, fixture(IFS), {})})
    backfill.single_runs(lake, http, budget(lake), points, "ecmwf_ifs", [RUN])
    backfill.single_runs(lake, http, budget(lake), points, "ecmwf_ifs", [RUN])

    (name,) = lake.names("raw", "backfill/")
    assert name == "backfill/single-runs/2024/03/20/20240320T000000Z-ecmwf_ifs.json.gz"
    _, metadata = lake.read("raw", name)
    assert metadata["run_init"] == RUN.isoformat()
    assert metadata["points"] == "torre-boldone,lime,ispra-jrc,varano-borghi"
    assert "run=2024-03-20T00%3A00" in metadata["request"]
    assert "forecast_hours=288" in metadata["request"]
    assert "past_hours" not in metadata["request"]
    assert len(replay.sent) == 1
    assert spent(lake) == 4


def test_a_run_open_meteo_lacks_is_not_asked_again(lake, points):
    http, replay = replaying({("GET", backfill.SINGLE): (400, NOT_AVAILABLE, {})})
    run = RUN.replace(hour=6)
    backfill.single_runs(lake, http, budget(lake), points, "ecmwf_ifs", [run])
    backfill.single_runs(lake, http, budget(lake), points, "ecmwf_ifs", [run])

    assert lake.names("raw", "backfill/") == [
        "backfill/single-runs/2024/03/20/20240320T060000Z-ecmwf_ifs.missing.json"
    ]
    assert len(replay.sent) == 1


def test_the_download_stops_at_the_day_budget(lake, points):
    http, replay = replaying({("GET", backfill.SINGLE): (200, fixture(IFS), {})})
    runs = [RUN, RUN.replace(hour=12)]

    assert not backfill.single_runs(lake, http, budget(lake, 6), points, "ecmwf_ifs", runs)
    assert len(lake.names("raw", "backfill/")) == 1
    assert len(replay.sent) == 1
    assert spent(lake) == 4


def test_previous_runs_ask_each_model_for_its_own_days(lake, points):
    http, replay = replaying({("GET", backfill.PREVIOUS): (200, fixture(D2), {})})
    models = ["icon_d2", "ukmo_global_deterministic_10km"]
    backfill.previous_runs(
        lake, http, budget(lake), points, models, date(2024, 3, 16), date(2024, 3, 17)
    )

    (name,) = lake.names("raw", "backfill/")
    assert name == "backfill/previous-runs/2024/03/16/20240316T000000Z-icon_d2-20240317.json.gz"
    (sent,) = replay.sent
    assert "start_date=2024-03-16&end_date=2024-03-17" in sent.url
    hourly = sent.url.split("hourly=", 1)[1].split("&", 1)[0].split("%2C")
    assert "temperature_2m_previous_day1" in hourly
    assert "wind_gusts_10m_previous_day1" in hourly
    assert "temperature_2m_previous_day2" not in hourly
    assert len(hourly) == 20
    assert spent(lake) == 8


def test_chunks_stay_on_the_two_week_grid():
    assert list(backfill.chunks(date(2024, 3, 14), date(2024, 3, 16))) == [
        (date(2024, 3, 2), date(2024, 3, 15)),
        (date(2024, 3, 16), date(2024, 3, 16)),
    ]


def test_previous_runs_cover_the_models_that_have_them():
    assert set(backfill.PREVIOUS_MODELS) == set(openmeteo.MODELS) - {"meteoswiss_icon_ch1"}


@pytest.fixture
def downloaded(lake, points):
    http, _ = replaying(
        {
            ("GET", backfill.SINGLE): (200, fixture(IFS), {}),
            ("GET", backfill.PREVIOUS): (200, fixture(D2), {}),
        }
    )
    backfill.single_runs(lake, http, budget(lake), points, "ecmwf_ifs", [RUN])
    backfill.previous_runs(
        lake, http, budget(lake), points, ["icon_d2"], date(2024, 3, 16), date(2024, 3, 17)
    )
    backfill.build(lake, date(2024, 3, 16), date(2024, 3, 22))
    return lake


def test_previous_runs_are_filed_by_valid_day_with_their_day_k(downloaded):
    rows = read_table(downloaded, "nwp_prev", date(2024, 3, 16))

    assert len(rows) == 4 * 24 * 2
    first = [r for r in rows if r["point"] == "torre-boldone"][:2]
    assert first[0]["source"] == "previous-runs"
    assert first[0]["run_init"] is None
    assert first[0]["lead_h"] is None
    assert first[0]["valid"] == first[1]["valid"] == "2024-03-16T00:00:00Z"
    by_day = {r["day_offset"]: r["temperature_2m"] for r in first}
    assert by_day == {0: pytest.approx(9.3), 1: pytest.approx(8.0)}


def test_single_runs_are_filed_by_valid_day_with_their_lead(downloaded):
    rows = read_table(downloaded, "nwp_prev", date(2024, 3, 20))

    assert len(rows) == 4 * 24
    first = next(r for r in rows if r["point"] == "torre-boldone")
    assert first["source"] == "single-runs"
    assert first["run_init"] == "2024-03-20T00:00:00Z"
    assert (first["lead_h"], first["day_offset"]) == (0, 0)
    assert first["temperature_2m"] == pytest.approx(8.3)
    later = read_table(downloaded, "nwp_prev", date(2024, 3, 22))
    assert {(r["lead_h"] // 24, r["day_offset"]) for r in later} == {(2, 2)}


def test_a_day_with_nothing_downloaded_has_no_file(downloaded):
    assert read_table(downloaded, "nwp_prev", date(2024, 3, 18)) == []


def test_overlap_counts_values_that_differ_from_the_live_archive(downloaded, tmp_path):
    files = [
        (downloaded.root / "curated" / compact.curated_name("nwp_prev", date(2024, 3, d)))
        for d in (20, 21)
    ]
    live = tmp_path / "live"
    live.mkdir()
    duckdb.connect().execute(
        "COPY (SELECT point, model, run_init, valid, temperature_2m "
        "+ CASE WHEN lead_h = 5 THEN 0.1 ELSE 0 END AS temperature_2m "
        f"FROM read_parquet({[f.as_posix() for f in files]})) "
        f"TO '{(live / 'nwp_hourly.parquet').as_posix()}' (FORMAT parquet)"
    )

    ((model, run, n, largest, _, over),) = backfill.overlap(
        downloaded.root, live, date(2024, 3, 20), date(2024, 3, 21)
    )
    assert (model, run, n, over) == ("ecmwf_ifs", "2024-03-20T00:00Z", 4 * 48, 4)
    assert largest == pytest.approx(0.1, abs=1e-4)
