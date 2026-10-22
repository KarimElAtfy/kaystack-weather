import logging
import re
import sys
from datetime import UTC, date, datetime, timedelta

import duckdb
import pytest
from conftest import TOWNS

from meteo import compact, jobs, mos, status

T = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


def test_an_unresolved_key_vault_reference_stops_the_arpa_job(lake):
    env = {
        "USER_AGENT": "weather.kaystack.dev github.com/KarimElAtfy/kaystack-weather",
        "ARPA_APP_TOKEN": "@Microsoft.KeyVault(SecretUri=https://kv-kaystack-meteo.vault.azure.net/secrets/arpa-app-token/)",
    }
    with pytest.raises(jobs.SourceFailed, match="Key Vault"):
        jobs.arpa_stations(lake, lake, env, TOWNS)
    assert lake.names("raw", "") == []


def test_a_source_that_fails_halfway_keeps_what_it_archived(lake):
    status.record(lake, "radar", T, {"sri": T}, {"sri"})

    def collect(newest):
        newest["sri"] = datetime(2026, 10, 16, 12, 5, tzinfo=UTC)
        raise ConnectionError("recorded for the test")

    assert not jobs._collect(lake, "radar", collect, {"sri"})
    radar = status.read(lake)["sources"]["radar"]
    assert radar["data_time"] == "2026-10-16T12:05:00Z"
    assert radar["checked_at"] == "2026-10-16T12:00:00Z"


@pytest.mark.parametrize(
    ("now", "last_complete_fetch", "due"),
    [
        ("2026-10-16T10:45:00Z", "2026-10-16T04:45:01Z", True),
        # The normal day: off the four hours, at most 5 h after a good slot.
        ("2026-10-16T05:45:00Z", "2026-10-16T04:45:01Z", False),
        ("2026-10-16T09:45:00Z", "2026-10-16T04:45:01Z", False),
        # The 04:45 slot failed, so the last complete fetch is the 22:45 one.
        ("2026-10-16T05:45:00Z", "2026-10-15T22:45:01Z", True),
        ("2026-10-16T06:45:00Z", "2026-10-16T05:45:02Z", False),
        ("2026-10-16T05:45:00Z", None, True),
    ],
)
def test_yr_is_asked_on_its_hours_and_again_after_a_failed_slot(now, last_complete_fetch, due):
    yr = {"checked_at": last_complete_fetch} if last_complete_fetch else {}
    current = {"sources": {"yr": yr}}
    assert jobs.yr_due(status.parse_stamp(now), current) is due


def test_the_nightly_rewrites_the_coefficients_of_the_day(lake, all_towns):
    day = date(2026, 10, 27)
    first, last = mos.window(day)
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    observed = "12 + 4 * sin(2 * pi() * hour(t) / 24)"
    tables = {
        "nwp_hourly": f"""SELECT 'torre-boldone' AS point, 'icon_d2' AS model,
            date_trunc('day', t - INTERVAL 1 HOUR) AS run_init, t AS valid,
            date_diff('hour', date_trunc('day', t - INTERVAL 1 HOUR), t)::SMALLINT AS lead_h,
            ({observed} + 1.5)::FLOAT AS temperature_2m""",
        "obs_arpa_hourly": f"SELECT 889 AS station, t AS hour_end, ({observed})::FLOAT AS t_at_end",
    }
    for n in range((last - first).days + 1):
        d = first + timedelta(days=n)
        start = f"TIMESTAMPTZ '{d} 01:00:00+00'"
        hours = f"range({start}, {start} + INTERVAL 1 DAY, INTERVAL 1 HOUR) r(t)"
        for table, query in tables.items():
            path = lake.root / "curated" / compact.curated_name(table, d)
            path.parent.mkdir(parents=True, exist_ok=True)
            con.execute(f"COPY ({query} FROM {hours}) TO '{path.as_posix()}' (FORMAT parquet)")
        path = lake.root / "curated" / compact.curated_name("obs_arpa_daily", d)
        path.parent.mkdir(parents=True, exist_ok=True)
        daily = f"SELECT 889 AS station, DATE '{d}' AS date, 16.0 AS tmax, 8.0 AS tmin, 144 AS n_t"
        con.execute(f"COPY ({daily}) TO '{path.as_posix()}' (FORMAT parquet)")

    jobs.mean60_coefficients(lake, all_towns, day)

    coefficients = mos.Coefficients.read(lake.read("curated", mos.name(day))[0])
    assert coefficients.correct("torre-boldone", "icon_d2", "t2m", 0, 13, 20.0) == 18.5
    assert coefficients.correct("ispra-jrc", "icon_d2", "t2m", 0, 13, 20.0) is None


# Recorded in WSL Ubuntu from /proc/self/status.
STATUS = "Name:\tgrep\nVmPeak:\t    4272 kB\nVmSize:\t    4272 kB\nVmHWM:\t    2304 kB\n"


def test_the_high_water_mark_is_read_in_mb():
    assert jobs.high_water_mb(STATUS) == 2
    assert jobs.high_water_mb("Name:\tgrep\n") is None


def test_each_step_logs_its_own_peak(caplog):
    with caplog.at_level(logging.INFO, logger="meteo.jobs"), jobs.step("compaction of 2026-10-20"):
        held = bytearray(30_000_000)
    del held
    (line,) = [r.getMessage() for r in caplog.records if "step peak" in r.getMessage()]
    peak = re.fullmatch(r"compaction of 2026-10-20: step peak (\d+|None) MB", line)
    assert peak
    if sys.platform == "linux":
        assert int(peak.group(1)) >= 30


def test_a_failed_30_day_pull_does_not_fail_the_night(lake, monkeypatch, caplog):
    monkeypatch.setattr(jobs, "radar_repair", lambda *a, **k: None)
    monkeypatch.setattr(jobs, "_arpa", lambda *a, **k: False)
    monkeypatch.setattr(compact, "days_due", lambda *a, **k: [])
    with caplog.at_level(logging.WARNING):
        jobs.nightly(lake, lake, {}, TOWNS, minutes=13, today=date(2026, 10, 22))
    assert "30-day ARPA pull failed" in caplog.text
