from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pytest

from meteo import compact, mos

POINT = "torre-boldone"
HOURS = (
    "range(TIMESTAMPTZ '2025-01-01 01:00:00+00', TIMESTAMPTZ '2025-04-01 00:00:00+00', "
    "INTERVAL 1 HOUR) r(t)"
)
# A daily cycle at the station. Each model is off by a fixed amount, GFS by one that
# changes with the hour.
OBSERVED = "10 + 3 * sin(2 * pi() * hour(t) / 24)"
LOCAL_DAY = "CAST(timezone('Europe/Rome', t - INTERVAL 1 MICROSECOND) AS DATE)"
TEN_MINUTES = (
    "date_diff('minute', timezone('Europe/Rome', {d}::TIMESTAMP), "
    "timezone('Europe/Rome', ({d} + 1)::TIMESTAMP)) // 10"
)


def write(path: Path, query: str) -> Path:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    con.execute(f"COPY ({query}) TO '{path.as_posix()}' (FORMAT parquet)")
    return path


def previous(model: str, day_offset: int, error: str, where: str = "true") -> str:
    return f"""
    SELECT '{POINT}' AS point, '{model}' AS model, 'previous-runs' AS source,
           NULL::TIMESTAMPTZ AS run_init, t AS valid, NULL::SMALLINT AS lead_h,
           {day_offset}::SMALLINT AS day_offset, ({OBSERVED} + {error})::FLOAT AS temperature_2m
    FROM {HOURS} WHERE {where}
    """


def run(model: str, run_init: str, valid: str, value: float) -> str:
    return f"""
    SELECT '{POINT}' AS point, '{model}' AS model, TIMESTAMPTZ '{run_init}' AS run_init,
           TIMESTAMPTZ '{valid}' AS valid,
           date_diff('hour', TIMESTAMPTZ '{run_init}', TIMESTAMPTZ '{valid}')::SMALLINT AS lead_h,
           {value}::FLOAT AS temperature_2m
    """


@pytest.fixture
def con(tmp_path):
    con = compact.connect(tmp_path)
    hourly = write(
        tmp_path / "arpa_hourly.parquet",
        f"SELECT 889 AS station, t AS hour_end, ({OBSERVED})::FLOAT AS t_at_end FROM {HOURS}",
    )
    daily = write(
        tmp_path / "arpa_daily.parquet",
        f"""SELECT 889 AS station, {LOCAL_DAY} AS date, max({OBSERVED})::FLOAT AS tmax,
                   min({OBSERVED})::FLOAT AS tmin, {TEN_MINUTES.format(d=LOCAL_DAY)} AS n_t
            FROM {HOURS} GROUP BY ALL""",
    )
    prev = write(
        tmp_path / "nwp_prev.parquet",
        " UNION ALL ".join(
            [
                previous("icon_d2", 0, "0.5"),
                # One hour short on 2025-03-10 in Rome, so that day has no Tmax.
                previous("icon_d2", 1, "1.0", "t <> TIMESTAMPTZ '2025-03-10 12:00:00+00'"),
                previous("gfs_global", 1, "-2 + 0.1 * hour(t)"),
            ]
        ),
    )
    runs = write(
        tmp_path / "nwp_hourly.parquet",
        " UNION ALL ".join(
            [
                run("ecmwf_ifs", "2025-03-01 00:00:00+00", "2025-03-02 13:00:00+00", 5.0),
                run("ecmwf_ifs", "2025-03-01 12:00:00+00", "2025-03-02 13:00:00+00", 7.0),
                run("icon_d2", "2025-01-01 12:00:00+00", "2025-01-02 13:00:00+00", 30.0),
            ]
        ),
    )
    mos.load(con, {POINT: 889}, [hourly], [daily], nwp_hourly=[runs], nwp_prev=[prev])
    return con


def forecast(con, model: str, valid: str) -> list[tuple]:
    return con.execute(
        "SELECT band, t2m FROM forecast WHERE model = ? AND valid = ?::TIMESTAMPTZ ORDER BY band",
        [model, valid],
    ).fetchall()


def test_the_window_ends_two_days_before_the_issue():
    assert mos.window(date(2026, 11, 10)) == (date(2026, 9, 10), date(2026, 11, 8))


def test_the_band_is_the_whole_days_of_lead_up_to_seven():
    run_init = datetime(2026, 10, 20, 0, tzinfo=UTC)
    bands = [
        mos.hourly_band(datetime(2026, 10, d, h, tzinfo=UTC), run_init)
        for d, h in [(20, 23), (21, 0), (28, 8)]
    ]
    assert bands == [0, 1, 7]


def test_each_model_learns_its_own_error_by_band_and_hour(con):
    coefficients = mos.Coefficients.read(mos.coefficients(con, date(2025, 3, 25)))

    assert coefficients.cells[(POINT, "icon_d2", "t2m", 0, 5)] == (0.5, 60)
    assert coefficients.cells[(POINT, "icon_d2", "t2m", 1, 5)] == (1.0, 60)
    assert coefficients.cells[(POINT, "gfs_global", "t2m", 1, 5)] == (-1.5, 60)
    assert coefficients.cells[(POINT, "gfs_global", "t2m", 1, 18)] == (-0.2, 60)
    assert coefficients.cells[(POINT, "gfs_global", "tmin", 1, None)][1] == 60
    assert coefficients.correct(POINT, "icon_d2", "t2m", 1, 5, 12.0) == 11.0


def test_the_newest_run_in_a_band_is_kept(con):
    assert forecast(con, "ecmwf_ifs", "2025-03-02 13:00:00+00") == [(1, 7.0)]


def test_a_run_takes_the_place_of_previous_runs_in_its_band(con):
    assert forecast(con, "icon_d2", "2025-01-02 13:00:00+00") == [
        (0, pytest.approx(10.5 + 3 * -0.2588, abs=1e-3)),
        (1, 30.0),
    ]


def test_a_model_short_of_45_pairs_stays_out_of_the_mean(con):
    coefficients = mos.Coefficients.read(mos.coefficients(con, date(2025, 2, 10)))

    assert coefficients.cells[(POINT, "icon_d2", "t2m", 1, 5)] == (1.0, 39)
    assert coefficients.correct(POINT, "icon_d2", "t2m", 1, 5, 12.0) is None


def test_a_daily_value_needs_every_hour_of_the_local_day(con):
    days = {
        d
        for (d,) in con.execute(
            "SELECT day FROM daily WHERE model = 'icon_d2' AND band = 1"
        ).fetchall()
    }
    assert date(2025, 3, 10) not in days
    # 23 hours long: the clocks went forward at 01:00 UTC.
    assert date(2025, 3, 30) in days


def test_the_hindcast_corrects_each_hour_with_its_issue_day(con):
    mos.hindcast(con, date(2025, 3, 20), date(2025, 3, 25))

    rows = con.execute(
        "SELECT band, count(*), max(abs(mean - observed)), min(m_models), max(m_models), "
        "max(high - low) FROM hindcast_hourly GROUP BY band ORDER BY band"
    ).fetchall()
    assert [(band, n, m_low, m_high) for band, n, _, m_low, m_high, _ in rows] == [
        (0, 6 * 24, 1, 1),
        (1, 6 * 24, 2, 2),
    ]
    assert all(worst < 1e-3 and spread < 1e-3 for _, _, worst, _, _, spread in rows)
    daily = con.execute(
        "SELECT variable, count(*), max(abs(mean - observed)) FROM hindcast_daily "
        "GROUP BY variable ORDER BY variable"
    ).fetchall()
    assert [(v, n) for v, n, _ in daily] == [("tmax", 6), ("tmin", 6)]
    assert all(worst < 1e-3 for _, _, worst in daily)
