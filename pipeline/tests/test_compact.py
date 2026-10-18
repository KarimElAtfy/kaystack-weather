"""Quality flags and daily tables built from ARPA pulls. The pulls are written in
the shape the live dataset returns; their values are made up to hit each rule."""

import gzip
import json
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from tables import compact_on_time, put_arpa, read_table

from meteo import compact, jobs
from meteo.store import raw_name
from meteo.towns import Sensor

DAY = date(2026, 10, 14)
PULLED = datetime(2026, 10, 15, 6, 0, tzinfo=UTC)
MISSING, INVALID, RANGE, SPIKE, FLATLINE, REVISED, BUDDY, SPECIAL, DUPLICATE = (
    1,
    2,
    4,
    8,
    16,
    32,
    64,
    128,
    256,
)


def series(sensor: int, operator: int, first_label: str, values: list, status="VA") -> list[dict]:
    start = datetime.fromisoformat(first_label)
    return [
        {
            "idsensore": str(sensor),
            "data": (start + timedelta(minutes=10 * i)).isoformat(timespec="milliseconds"),
            "valore": str(v),
            "idoperatore": str(operator),
            "stato": status,
        }
        for i, v in enumerate(values)
    ]


def flags(lake, sensor: int, operator: int = 1) -> dict[str, int]:
    rows = read_table(lake, "obs_arpa", DAY)
    return {
        r["end"][11:16]: r["qc"]
        for r in rows
        if r["sensor"] == sensor and r["operator"] == operator
    }


def build(lake, all_towns, records: list[dict], pulled=PULLED) -> None:
    put_arpa(lake, pulled, records)
    compact_on_time(lake, all_towns, DAY)


def test_missing_invalid_and_out_of_range_values(lake, all_towns):
    records = series(8145, 1, "2026-10-14T13:10:00", [12.0, -9999, 50.0])
    records += series(8145, 1, "2026-10-14T13:40:00", [12.5], status="NA")
    # What the live dataset actually sends for a missing value.
    records += series(8145, 1, "2026-10-14T13:50:00", [-999], status="NA")
    build(lake, all_towns, records)
    assert flags(lake, 8145) == {
        "12:10": 0,
        "12:20": MISSING,
        "12:30": RANGE,
        "12:40": INVALID,
        "12:50": MISSING | INVALID,
    }


def test_a_spike_up_and_back_is_flagged(lake, all_towns):
    build(lake, all_towns, series(8145, 1, "2026-10-14T13:10:00", [10.0, 10.2, 15.0, 10.1, 10.0]))
    assert flags(lake, 8145) == {"12:10": 0, "12:20": 0, "12:30": SPIKE, "12:40": 0, "12:50": 0}


def test_three_flat_hours_of_temperature_are_flagged(lake, all_towns):
    flat = series(8145, 1, "2026-10-14T03:10:00", [11.3] * 18 + [11.4])
    short = series(32353, 1, "2026-10-14T03:10:00", [11.3] * 17 + [11.4])
    rain = series(8161, 4, "2026-10-14T03:10:00", [0.0] * 30)
    build(lake, all_towns, flat + short + rain)
    assert set(flags(lake, 8145).values()) == {0, FLATLINE}
    assert sum(1 for q in flags(lake, 8145).values() if q == FLATLINE) == 18
    assert set(flags(lake, 32353).values()) == {0}
    assert set(flags(lake, 8161, 4).values()) == {0}


def test_a_revised_value_is_kept_from_the_newest_pull(lake, all_towns):
    put_arpa(lake, PULLED - timedelta(hours=3), series(8145, 1, "2026-10-14T13:10:00", [12.0]))
    build(lake, all_towns, series(8145, 1, "2026-10-14T13:10:00", [12.4]))
    (row,) = read_table(lake, "obs_arpa", DAY)
    assert row["value"] == pytest.approx(12.4)
    assert row["qc"] == REVISED
    assert row["first_seen"] == "2026-10-15T03:00:00Z"
    assert row["last_seen"] == "2026-10-15T06:00:00Z"


def test_two_values_for_one_key_in_one_pull_are_flagged(lake, all_towns):
    records = series(8145, 1, "2026-10-14T13:10:00", [12.0]) + series(
        8145, 1, "2026-10-14T13:10:00", [12.2]
    )
    build(lake, all_towns, records)
    assert flags(lake, 8145) == {"12:10": DUPLICATE}


def test_rain_at_zero_beside_a_wet_buddy_is_flagged(lake, all_towns):
    station = series(8161, 4, "2026-10-14T10:10:00", [0.0] * 18)
    buddy = series(5857, 4, "2026-10-14T10:10:00", [0.2] * 18)
    build(lake, all_towns, station + buddy)
    assert set(flags(lake, 8161, 4).values()) == {BUDDY}
    assert set(flags(lake, 5857, 4).values()) == {0}


def test_temperature_far_from_its_buddy_for_three_hours_is_flagged(lake, all_towns):
    station = series(8145, 1, "2026-10-14T10:10:00", [20.0, 20.1] * 15)
    # 4 C or more below the station, beyond the +3.4 C band, for the first four hours.
    buddy = series(5864, 1, "2026-10-14T10:10:00", [16.0] * 24 + [19.0] * 6)
    build(lake, all_towns, station + buddy)
    by_end = flags(lake, 8145)
    assert [end for end, q in by_end.items() if q == BUDDY] == list(by_end)[:24]
    assert set(list(by_end.values())[24:]) == {0}


def test_two_hours_far_from_the_buddy_are_not_enough(lake, all_towns):
    station = series(8145, 1, "2026-10-14T10:10:00", [20.0, 20.1] * 12)
    buddy = series(5864, 1, "2026-10-14T10:10:00", [16.0] * 12 + [19.0] * 12)
    build(lake, all_towns, station + buddy)
    assert set(flags(lake, 8145).values()) == {0}


def test_wind_codes_gusts_and_rain_limits(lake):
    sensors = [
        Sensor(14536, "wind_direction", 1375),
        Sensor(14537, "wind_speed", 1375),
        Sensor(14527, "precipitation", 1375),
    ]
    records = series(14536, 1, "2026-10-14T13:10:00", [777, 210])
    records += series(14537, 1, "2026-10-14T13:10:00", [3.0, 2.0])
    records += series(14537, 3, "2026-10-14T13:10:00", [2.5, 4.0])
    records += series(14527, 4, "2026-10-14T13:10:00", [60.0])
    put_arpa(lake, PULLED, records)
    compact.run(lake, DAY, sensors, {}, [], deadline=1e12, today=DAY + timedelta(days=2))

    rows = {
        (r["sensor"], r["operator"], r["end"][11:16]): r for r in read_table(lake, "obs_arpa", DAY)
    }
    assert rows[(14536, 1, "12:10")]["value"] is None
    assert rows[(14536, 1, "12:10")]["qc"] == SPECIAL
    assert rows[(14536, 1, "12:20")]["qc"] == 0
    assert rows[(14537, 3, "12:10")]["qc"] == RANGE
    assert rows[(14537, 3, "12:20")]["qc"] == 0
    assert rows[(14527, 4, "12:10")]["qc"] == RANGE


def test_the_value_ending_at_midnight_belongs_to_the_day_before(lake, all_towns):
    # Labels 01:00 and 01:10 on the 15th in UTC+1 end at 00:00 and 00:10 UTC.
    build(lake, all_towns, series(8145, 1, "2026-10-15T01:00:00", [9.0, 9.1]))
    assert flags(lake, 8145) == {"00:00": 0}


@pytest.mark.parametrize(("day", "values"), [(date(2026, 10, 14), 144), (date(2026, 10, 25), 150)])
def test_a_local_day_is_complete_with_every_ten_minute_value(lake, all_towns, day, values):
    # Local day D starts at 00:00 Europe/Rome; the first value ends 10 minutes later.
    start = datetime(day.year, day.month, day.day, tzinfo=UTC) - timedelta(hours=2)
    first_label = (start + timedelta(hours=1, minutes=10)).replace(tzinfo=None).isoformat()
    temps = series(14528, 1, first_label, [10.0 + (i % 7) * 0.1 for i in range(values)])
    put_arpa(lake, datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(days=1), temps)
    compact_on_time(lake, all_towns, day)

    (daily,) = read_table(lake, "obs_arpa_daily", day)
    assert daily["station"] == 1375
    assert daily["n_t"] == values
    assert daily["complete"] is True
    assert daily["tmax"] == pytest.approx(10.6)


def test_a_day_with_a_gap_is_not_complete(lake, all_towns):
    start = datetime(2026, 10, 13, 22, 0, tzinfo=UTC)
    first_label = (start + timedelta(hours=1, minutes=10)).replace(tzinfo=None).isoformat()
    put_arpa(lake, PULLED, series(14528, 1, first_label, [10.0] * 143))
    compact_on_time(lake, all_towns, DAY)
    (daily,) = read_table(lake, "obs_arpa_daily", DAY)
    assert daily["complete"] is False


def test_completeness_counts_values_per_sensor(lake, all_towns):
    build(lake, all_towns, series(8145, 1, "2026-10-14T13:10:00", [12.0] * 6))
    counts = json.loads(lake.read("curated", "completeness/2026-10-14.json")[0])
    assert counts["arpa"] == {"8145/1": 6}
    assert counts["radar"] == {"expected": 288, "frames": 0, "source_gaps": None}


def test_due_days_include_earlier_ones_left_unfinished(lake):
    today = date(2026, 10, 20)
    lake.put("curated", compact.completeness_name(date(2026, 10, 16)), b"{}", "")
    assert compact.days_due(lake, today) == [
        date(2026, 10, 18),
        date(2026, 10, 17),
        date(2026, 10, 15),
    ]


def test_a_later_30_day_pull_revises_a_compacted_day(lake, all_towns):
    build(lake, all_towns, series(8145, 1, "2026-10-14T13:10:00", [12.0]))
    late = datetime(2026, 11, 2, 1, 30, tzinfo=UTC)
    put_arpa(lake, late, series(8145, 1, "2026-10-14T13:10:00", [12.6]), variant="revision")
    # A live pull that late is not read for this day.
    put_arpa(lake, late, series(8145, 1, "2026-10-14T13:10:00", [99.0]))
    compact_on_time(lake, all_towns, DAY)

    (row,) = read_table(lake, "obs_arpa", DAY)
    assert row["value"] == pytest.approx(12.6)
    assert row["qc"] == REVISED
    assert row["last_seen"] == "2026-11-02T01:30:00Z"


def test_the_portal_csv_is_read_like_a_pull(lake, all_towns):
    csv_text = (
        "idsensore,data,valore,idoperatore,stato\r\n8145,2026-10-14T13:10:00.000,12.30,1,VA\r\n"
    )
    name = raw_name("arpa", datetime(2026, 10, 15, 22, 2, 52, tzinfo=UTC), "portal-csv", "csv.gz")
    lake.put_new("raw", name, gzip.compress(csv_text.encode()), "application/gzip")
    compact_on_time(lake, all_towns, DAY)
    (row,) = read_table(lake, "obs_arpa", DAY)
    assert row["value"] == pytest.approx(12.3)
    assert row["end"] == "2026-10-14T12:10:00Z"


def test_a_day_near_the_open_meteo_expiry_keeps_its_model_tables(lake, all_towns):
    lake.put("curated", compact.curated_name("nwp_hourly", DAY), b"complete", "")
    lake.put("curated", compact.completeness_name(DAY), b"{}", "")
    jobs.compact_day(lake, all_towns, DAY, deadline=1e12, today=DAY + timedelta(days=86))
    assert lake.read("curated", compact.curated_name("nwp_hourly", DAY))[0] == b"complete"
    assert lake.read("curated", compact.completeness_name(DAY))[0] == b"{}"


# The Azure worker runs the jobs with no __main__ module at all.
WITHOUT_MAIN = """
import pathlib, sys
del sys.modules["__main__"]
from meteo import compact
print(compact.connect(pathlib.Path(sys.argv[1])).execute("SELECT 42").fetchone()[0])
"""


def test_duckdb_loads_in_a_worker_without_main(tmp_path):
    out = subprocess.run(
        [sys.executable, "-c", WITHOUT_MAIN, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "42"
