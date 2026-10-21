import json
from datetime import UTC, datetime, timedelta

from meteo import status
from meteo.contract import Status

T = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
AIRPORTS = ("LIME", "LIMC")


def entry(lake, source: str) -> dict:
    return status.read(lake)["sources"][source]


def test_data_time_is_the_oldest_station_so_one_dead_station_shows(lake):
    first = {"LIME": T - timedelta(minutes=10), "LIMC": T - timedelta(minutes=40)}
    status.record(lake, "metar", T, first, AIRPORTS)
    later = {"LIME": T + timedelta(minutes=20)}
    status.record(lake, "metar", T + timedelta(minutes=30), later, AIRPORTS)

    metar = entry(lake, "metar")
    assert metar["data_time"] == "2026-10-16T11:20:00Z"
    assert metar["checked_at"] == "2026-10-16T12:30:00Z"
    assert metar["parts"] == {"LIMC": "2026-10-16T11:20:00Z", "LIME": "2026-10-16T12:20:00Z"}


def test_model_runs_count_from_the_newest_one(lake):
    runs = {"icon_d2": T - timedelta(hours=1), "ecmwf_ifs": T - timedelta(hours=7)}
    status.record(lake, "open-meteo", T, runs, runs.keys())
    assert entry(lake, "open-meteo")["data_time"] == "2026-10-16T11:00:00Z"


def test_a_part_no_longer_expected_stops_holding_data_time_back(lake):
    status.record(lake, "arpa", T, {"8145": T - timedelta(days=3), "8161": T}, ("8145", "8161"))
    # Sensor 8145 replaced by a new id: it leaves the town files and the status.
    status.record(lake, "arpa", T, {"9999": T}, ("8161", "9999"))
    arpa = entry(lake, "arpa")
    assert arpa["parts"] == {"8161": "2026-10-16T12:00:00Z", "9999": "2026-10-16T12:00:00Z"}
    assert arpa["data_time"] == "2026-10-16T12:00:00Z"


def test_a_failed_check_keeps_the_last_good_one(lake):
    status.record(lake, "radar", T, {"sri": T - timedelta(minutes=10)}, {"sri"})
    status.record(lake, "radar", None, {"sri": T - timedelta(minutes=5)}, {"sri"})
    radar = entry(lake, "radar")
    assert radar["checked_at"] == "2026-10-16T12:00:00Z"
    assert radar["data_time"] == "2026-10-16T11:55:00Z"


def test_status_json_is_the_contract_file_freshness_reads(lake):
    status.record(lake, "yr", T, {"lime": T}, {"lime"})
    body = lake.read_versioned("public", "status.json")[0]
    assert Status.model_validate_json(body).schema_ == "status/1"
    assert status.parse_stamp(json.loads(body)["sources"]["yr"]["data_time"]) == T


def test_a_source_never_reached_has_null_times(lake):
    status.record(lake, "mosmix", None, {}, {"16076"})
    assert entry(lake, "mosmix") == {"checked_at": None, "data_time": None, "parts": {}}
    assert "mosmix data_time" in status.late_sources(status.read(lake), T)


def test_a_file_written_before_the_contract_is_carried_over(lake):
    old = {"generated_at": "2026-10-16T11:00:00Z", "sources": {"yr": {"parts": {}}}}
    lake.put("public", "status.json", json.dumps(old).encode(), "application/json")
    status.record(lake, "radar", T, {"sri": T}, {"sri"})
    assert entry(lake, "yr") == {"checked_at": None, "data_time": None, "parts": {}}
    assert entry(lake, "radar")["data_time"] == "2026-10-16T12:00:00Z"


def test_late_sources_by_data_and_by_check():
    stamp = status.stamp
    sources = {source: {"checked_at": stamp(T), "data_time": stamp(T)} for source in status.LIMITS}
    sources["radar"]["data_time"] = stamp(T - timedelta(minutes=31))
    sources["arpa"]["checked_at"] = stamp(T - timedelta(hours=10))
    del sources["yr"]
    late = status.late_sources({"sources": sources}, T)
    assert late == ["radar data_time", "arpa checked_at", "yr data_time", "yr checked_at"]
