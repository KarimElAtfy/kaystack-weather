"""The time conventions in docs/time-conventions.md, one test each, named after the rule."""

import gzip
import json
import re
from datetime import UTC, date, datetime, timedelta

import pytest
from conftest import fixture
from tables import compact_on_time, put_arpa, put_ensemble, read_table

from meteo import arpa, mosmix, openmeteo, yr


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("2026-07-01T14:10:00.000", "2026-07-01T13:10:00"),
        ("2026-01-15T14:10:00.000", "2026-01-15T13:10:00"),
        ("2026-10-25T02:30:00.000", "2026-10-25T01:30:00"),
        ("2026-03-29T00:00:00.000", "2026-03-28T23:00:00"),
    ],
)
def test_t1_arpa_label_is_utc_plus_one_all_year(label, expected):
    assert arpa.to_utc(label) == utc(expected)


def ten_minutes(sensor: int, operator: int, first_label: str, values: list[float]) -> list[dict]:
    start = datetime.fromisoformat(first_label)
    return [
        {
            "idsensore": str(sensor),
            "data": (start + timedelta(minutes=10 * i)).isoformat(timespec="milliseconds"),
            "valore": f"{v:.2f}",
            "idoperatore": str(operator),
            "stato": "VA",
        }
        for i, v in enumerate(values)
    ]


def test_t3_hourly_rain_sums_the_six_values_ending_in_the_hour(lake, all_towns):
    # Labels 13:10 to 14:00 in UTC+1 end at 12:10 to 13:00 UTC: the hour ending 13:00.
    rain = ten_minutes(8161, 4, "2026-10-14T13:10:00", [0.2, 0.4, 0.0, 0.2, 0.0, 0.2])
    rain += ten_minutes(8161, 4, "2026-10-14T14:10:00", [0.2, 0.2, 0.2, 0.2, 0.2])
    put_arpa(lake, utc("2026-10-15T06:00:00"), rain)
    compact_on_time(lake, all_towns, date(2026, 10, 14))

    hours = {r["hour_end"]: r for r in read_table(lake, "obs_arpa_hourly", date(2026, 10, 14))}
    assert hours["2026-10-14T13:00:00Z"]["pr_1h"] == pytest.approx(1.0)
    assert hours["2026-10-14T13:00:00Z"]["n_pr"] == 6
    # Five of six values: the hour is not complete, so no total.
    assert hours["2026-10-14T14:00:00Z"]["pr_1h"] is None
    assert hours["2026-10-14T14:00:00Z"]["n_pr"] == 5


def test_t4_temperature_at_h_is_the_mean_ending_at_h(lake, all_towns):
    # The label 14:00 ends at 13:00 UTC.
    temps = ten_minutes(8145, 1, "2026-10-14T13:10:00", [10.0, 10.5, 11.0, 11.5, 12.0, 12.5])
    put_arpa(lake, utc("2026-10-15T06:00:00"), temps)
    compact_on_time(lake, all_towns, date(2026, 10, 14))

    (hour,) = read_table(lake, "obs_arpa_hourly", date(2026, 10, 14))
    assert hour["hour_end"] == "2026-10-14T13:00:00Z"
    assert hour["t_at_end"] == pytest.approx(12.5)
    assert hour["t_mean"] == pytest.approx(11.25)


def test_t5_open_meteo_times_are_utc():
    for answer in json.loads(fixture("open-meteo/forecast-icon_d2-run.json")):
        assert answer["utc_offset_seconds"] == 0
        assert answer["timezone"] == "GMT"


def test_t6_open_meteo_rows_start_at_the_run():
    run_init = utc("2026-10-16T09:00:00")
    metadata = {
        "run_init": run_init.isoformat(),
        "run_available": "2026-10-16T10:26:24+00:00",
        "fetched_at": "2026-10-16T12:21:00+00:00",
        "points": "torre-boldone,ispra-jrc,varano-borghi,lime",
    }
    raw = gzip.compress(fixture("open-meteo/forecast-icon_d2-run.json"))
    rows = list(openmeteo.hourly_rows(raw, metadata, "icon_d2"))
    assert min(r["valid"] for r in rows) == run_init
    first = next(r for r in rows if r["point"] == "lime")
    assert first["lead_h"] == 0
    assert all(r["lead_h"] == (r["valid"] - run_init) / timedelta(hours=1) for r in rows)


def test_t7_metar_obs_time_agrees_with_the_report_group():
    for report in json.loads(fixture("metar/awc-metar-sample.json")):
        obs = datetime.fromtimestamp(report["obsTime"], UTC)
        group = re.search(r"\b(\d{6})Z\b", report["rawOb"]).group(1)
        assert group == obs.strftime("%d%H%M")


def test_t8_mosmix_kelvin_and_extreme_steps():
    rows = list(mosmix.rows(fixture("mosmix/MOSMIX_L_LATEST_16076.kmz")))
    assert {r["issue"] for r in rows} == {utc("2026-10-16T09:00:00")}
    assert all(r["valid"].tzinfo == UTC for r in rows)
    assert {r["valid"].hour for r in rows if r["tx_c"] is not None} == {18}
    assert {r["valid"].hour for r in rows if r["tn_c"] is not None} == {6}
    assert -10 < rows[0]["t_c"] < 35


def test_t9_yr_amounts_end_an_hour_after_their_step():
    raw = fixture("yr/locationforecast-complete-torre-boldone.json")
    steps = json.loads(raw)["properties"]["timeseries"]
    rows = {
        r["valid"]: r
        for r in yr.rows(gzip.compress(raw), "torre-boldone", utc("2026-10-16T12:10:00"))
    }
    first = steps[0]
    end = datetime.fromisoformat(first["time"]) + timedelta(hours=1)
    expected = first["data"]["next_1_hours"]["details"]["precipitation_amount"]
    assert rows[end]["pr_1h_end"] == expected
    assert "pr_1h_end" not in rows[datetime.fromisoformat(first["time"])]


def test_t10_radar_key_names_the_frame_in_utc():
    (product,) = json.loads(fixture("radar/findLastProductByType-SRI.json"))["lastProducts"]
    frame = datetime.fromtimestamp(product["time"] / 1000, UTC)
    assert frame == utc("2026-10-16T12:00:00")
    link = json.loads(fixture("radar/downloadProduct-SRI-redacted.json"))
    assert link["key"] == f"SRI/{utc('2026-10-15T17:00:00'):%d-%m-%Y-%H-%M}.tif"


def test_t11_six_hour_blocks_end_at_synoptic_hours(lake, all_towns):
    run_init = utc("2026-10-14T00:00:00")
    hours = [run_init + timedelta(hours=h) for h in range(0, 31)]
    put_ensemble(lake, run_init, hours, members=3, t2m=lambda m, t: 10.0, pr=lambda m, t: 0.5)
    compact_on_time(lake, all_towns, date(2026, 10, 14))

    blocks = [
        r for r in read_table(lake, "ens_window", date(2026, 10, 14)) if r["kind"] == "6h_utc"
    ]
    assert [b["end"][11:16] for b in blocks] == ["06:00", "12:00", "18:00", "00:00", "06:00"]
    # Lead 0 holds the hour before the run, which is not used: (00, 06] has 6 hours.
    assert all(b["pr_mean"] == pytest.approx(3.0) for b in blocks)


@pytest.mark.parametrize(
    ("day", "hours"),
    [(date(2026, 3, 29), 23), (date(2026, 10, 25), 25), (date(2026, 10, 14), 24)],
)
def test_t12_a_local_day_has_23_or_25_hours_when_the_clocks_change(lake, all_towns, day, hours):
    run_init = datetime(day.year, day.month, day.day, tzinfo=UTC) - timedelta(days=1)
    valid = [run_init + timedelta(hours=h) for h in range(0, 72)]
    put_ensemble(lake, run_init, valid, members=2, t2m=lambda m, t: t.hour, pr=lambda m, t: 0.0)
    compact_on_time(lake, all_towns, run_init.date())

    days = [
        r
        for r in read_table(lake, "ens_window", run_init.date())
        if r["kind"] == "day_local" and r["start"][:10] == (day - timedelta(days=1)).isoformat()
    ]
    (local_day,) = days
    start, end = utc(local_day["start"][:19]), utc(local_day["end"][:19])
    assert (end - start) / timedelta(hours=1) == hours


def test_t13_thresholds_include_the_threshold_itself(lake, all_towns):
    run_init = utc("2026-10-14T00:00:00")
    valid = [run_init + timedelta(hours=h) for h in range(0, 8)]

    # Members 0 and 1 reach exactly 0.2 mm every hour and exactly 1.0 mm over (00, 06].
    def pr(member: int, t: datetime) -> float:
        if member < 2:
            return 0.25 if t.hour in (1, 2, 3, 4) else 0.2
        return 0.1

    put_ensemble(lake, run_init, valid, members=4, t2m=lambda m, t: 5.0, pr=pr)
    compact_on_time(lake, all_towns, date(2026, 10, 14))

    hourly = read_table(lake, "ens_hourly", date(2026, 10, 14))
    assert [r["pr_p_ge_0_2"] for r in hourly] == [0.5] * len(valid)
    (block,) = [
        r for r in read_table(lake, "ens_window", date(2026, 10, 14)) if r["kind"] == "6h_utc"
    ]
    assert block["pr_p_ge_1"] == 0.5
