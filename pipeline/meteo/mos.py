"""mean60-v1, the temperature correction of v0.1.

Each model is corrected by its own mean error over the 60 days that end two days
before the issue, and the corrected models are averaged with equal weights. The
error is learnt against the reference station per point, model, lead band and UTC
hour for the hourly temperature, and per point, model and lead band for the maximum
and the minimum of the local day (T12 in docs/time-conventions.md). A model with
fewer than 45 pairs in a cell stays out of the mean there.

The lead band of an hourly value is floor(lead / 24 h), at most 7. A model has
several runs in a band at each valid hour and the pairs use the newest. Open-Meteo
Previous Runs serves the same value as day k for most models; over 18-20 October
2026 it did not for AIFS at day 0 (-0.19 °C on average), UKMO at day 2 (+0.12 °C)
and ICON-EU at day 1 (+0.03 °C). The daily maximum and minimum of band k are taken
over those values, on the local days the model has every hour of.

At issue time a daily value is in band k when its local day is k days after the
local day of the issue, and its hours come from one run with leads on both sides
of 24k h. That run is a few hours older than the ones behind the pairs, the same
gap there is between Previous Runs and a live issue.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Self

METHOD = "mean60-v1"
WINDOW_DAYS = 60
# ARPA's data for day D is complete at D+2, when the nightly compacts it.
EMBARGO_DAYS = 2
MIN_PAIRS = 45
LAST_BAND = 7

type Key = tuple[str, str, str, int, int | None]


def name(day: date) -> str:
    return f"models/mean60/{day:%Y-%m-%d}.json"


def window(day: date) -> tuple[date, date]:
    """The first and the last day of the pairs behind the coefficients of `day`: UTC
    days of the valid time for hourly values, local days for daily ones."""
    last = day - timedelta(days=EMBARGO_DAYS)
    return last - timedelta(days=WINDOW_DAYS - 1), last


def hourly_band(valid: datetime, run_init: datetime) -> int:
    return min((valid - run_init) // timedelta(hours=24), LAST_BAND)


def _paths(paths: Sequence[Path]) -> str:
    return f"read_parquet({[p.as_posix() for p in paths]!r}, union_by_name = true)"


def load(
    con,
    stations: dict[str, int],
    arpa_hourly: Sequence[Path],
    arpa_daily: Sequence[Path],
    nwp_hourly: Sequence[Path] = (),
    nwp_prev: Sequence[Path] = (),
) -> None:
    """Creates `forecast`, one temperature per point, model, band and valid hour, then
    `daily`, `observed` and `observed_daily`, from curated files. `stations` maps the
    forecast points to their ARPA station."""
    # Days and hours below are UTC ones, whatever the zone of the machine.
    con.execute("SET TimeZone = 'UTC'")
    runs = [
        f"SELECT point, model, run_init, valid, lead_h, temperature_2m FROM {_paths(p)}"
        for p in (nwp_hourly, nwp_prev)
        if p
    ]
    if not runs:
        raise ValueError("no forecast files")
    con.execute(f"""
    CREATE OR REPLACE TABLE forecast AS
    SELECT point, model, least(lead_h // 24, {LAST_BAND}) AS band, valid, temperature_2m AS t2m
    FROM ({" UNION ALL ".join(runs)})
    WHERE run_init IS NOT NULL AND lead_h >= 0 AND temperature_2m IS NOT NULL
    QUALIFY row_number() OVER (PARTITION BY point, model, band, valid ORDER BY run_init DESC) = 1
    """)
    if nwp_prev:
        con.execute(f"""
        INSERT INTO forecast
        SELECT p.point, p.model, least(p.day_offset, {LAST_BAND}), p.valid, p.temperature_2m
        FROM {_paths(nwp_prev)} p
        ANTI JOIN forecast f
          ON f.point = p.point AND f.model = p.model AND f.band = least(p.day_offset, {LAST_BAND})
         AND f.valid = p.valid
        WHERE p.source = 'previous-runs' AND p.temperature_2m IS NOT NULL
        """)

    # T12: the local day D takes the instants in (D 00:00, D+1 00:00], so 23, 24 or
    # 25 of them. A day the model misses an hour of would pull Tmax down.
    con.execute("""
    CREATE OR REPLACE TABLE daily AS
    SELECT point, model, band, day, max(t2m) AS tmax, min(t2m) AS tmin
    FROM (
        SELECT *, CAST(timezone('Europe/Rome', valid - INTERVAL 1 MICROSECOND) AS DATE) AS day
        FROM forecast WHERE band >= 1
    )
    GROUP BY point, model, band, day
    HAVING count(*) = date_diff(
        'hour', timezone('Europe/Rome', day::TIMESTAMP),
        timezone('Europe/Rome', (day + 1)::TIMESTAMP)
    )
    """)

    con.execute("CREATE OR REPLACE TABLE stations (point VARCHAR, station INTEGER)")
    con.executemany("INSERT INTO stations VALUES (?, ?)", list(stations.items()))
    con.execute(f"""
    CREATE OR REPLACE TABLE observed AS
    SELECT s.point, o.hour_end AS valid, o.t_at_end AS t
    FROM {_paths(arpa_hourly)} o JOIN stations s USING (station)
    WHERE o.t_at_end IS NOT NULL
    """)
    # A day counts with at most an hour of its 10-minute temperatures missing, and a
    # gap in the rain does not matter here. Requiring all of them left Ispra JRC with
    # 284 days of 364 in 2025, too few for 45 pairs in many windows.
    con.execute(f"""
    CREATE OR REPLACE TABLE observed_daily AS
    SELECT s.point, o.date AS day, o.tmax, o.tmin
    FROM {_paths(arpa_daily)} o JOIN stations s USING (station)
    WHERE o.n_t >= date_diff(
        'minute', timezone('Europe/Rome', o.date::TIMESTAMP),
        timezone('Europe/Rome', (o.date + 1)::TIMESTAMP)
    ) // 10 - 6
    """)


COEFFICIENTS = """
SELECT f.point, f.model, 't2m' AS variable, f.band, hour(f.valid) AS hour_utc,
       round(avg(f.t2m - o.t), 3) AS bias, count(*) AS n_pairs
FROM forecast f JOIN observed o USING (point, valid)
WHERE CAST(f.valid AS DATE) BETWEEN $first AND $last
GROUP BY f.point, f.model, f.band, hour(f.valid)
UNION ALL
SELECT d.point, d.model, 'tmax', d.band, NULL, round(avg(d.tmax - o.tmax), 3), count(*)
FROM daily d JOIN observed_daily o USING (point, day)
WHERE d.day BETWEEN $first AND $last
GROUP BY d.point, d.model, d.band
UNION ALL
SELECT d.point, d.model, 'tmin', d.band, NULL, round(avg(d.tmin - o.tmin), 3), count(*)
FROM daily d JOIN observed_daily o USING (point, day)
WHERE d.day BETWEEN $first AND $last
GROUP BY d.point, d.model, d.band
ORDER BY 1, 2, 3, 4, 5
"""
COLUMNS = ["point", "model", "variable", "lead_band", "hour_utc", "bias", "n_pairs"]


def coefficients(con, day: date) -> bytes:
    """The coefficients file of `day`, from the tables `load` made. Cells under
    MIN_PAIRS are kept with their count."""
    first, last = window(day)
    rows = con.execute(COEFFICIENTS, {"first": first, "last": last}).fetchall()
    body = {
        "method": METHOD,
        "day": day.isoformat(),
        "window": [first.isoformat(), last.isoformat()],
        "min_pairs": MIN_PAIRS,
        "columns": COLUMNS,
        "rows": [list(r) for r in rows],
    }
    return json.dumps(body, separators=(",", ":")).encode()


@dataclass(frozen=True)
class Coefficients:
    day: date
    cells: dict[Key, tuple[float, int]]

    @classmethod
    def read(cls, body: bytes) -> Self:
        data = json.loads(body)
        if data["method"] != METHOD:
            raise ValueError(f"coefficients of {data['method']}, not {METHOD}")
        cells = {(p, m, v, b, h): (bias, n) for p, m, v, b, h, bias, n in data["rows"]}
        return cls(date.fromisoformat(data["day"]), cells)

    def correct(
        self, point: str, model: str, variable: str, band: int, hour_utc: int | None, value: float
    ) -> float | None:
        """None when the model has too few pairs there to enter the mean."""
        bias, n = self.cells.get((point, model, variable, band, hour_utc), (0.0, 0))
        return value - bias if n >= MIN_PAIRS else None


# Each hourly value is corrected with the coefficients of the day it was issued on,
# taken as its valid day less its band, and each daily one with those of its local
# day less its band.
HINDCAST_HOURLY = f"""
SELECT f.point, f.band, f.valid, avg(f.t2m - c.bias) AS mean, min(f.t2m - c.bias) AS low,
       max(f.t2m - c.bias) AS high, count(*) AS m_models, any_value(o.t) AS observed
FROM forecast f
JOIN coefficients c
  ON c.day = CAST(f.valid AS DATE) - f.band AND c.point = f.point AND c.model = f.model
 AND c.variable = 't2m' AND c.band = f.band AND c.hour_utc = hour(f.valid)
 AND c.n_pairs >= {MIN_PAIRS}
LEFT JOIN observed o ON o.point = f.point AND o.valid = f.valid
WHERE CAST(f.valid AS DATE) BETWEEN $first AND $last
GROUP BY f.point, f.band, f.valid
"""
HINDCAST_DAILY = f"""
SELECT d.point, d.band, d.day, c.variable,
       avg(CASE c.variable WHEN 'tmax' THEN d.tmax ELSE d.tmin END - c.bias) AS mean,
       min(CASE c.variable WHEN 'tmax' THEN d.tmax ELSE d.tmin END - c.bias) AS low,
       max(CASE c.variable WHEN 'tmax' THEN d.tmax ELSE d.tmin END - c.bias) AS high,
       count(*) AS m_models,
       any_value(CASE c.variable WHEN 'tmax' THEN o.tmax ELSE o.tmin END) AS observed
FROM daily d
JOIN coefficients c
  ON c.day = d.day - d.band AND c.point = d.point AND c.model = d.model
 AND c.variable IN ('tmax', 'tmin') AND c.band = d.band AND c.n_pairs >= {MIN_PAIRS}
LEFT JOIN observed_daily o ON o.point = d.point AND o.day = d.day
WHERE d.day BETWEEN $first AND $last
GROUP BY d.point, d.band, d.day, c.variable
"""


def hindcast(con, first: date, last: date) -> None:
    """Corrects every forecast valid from `first` to `last` as the site would have,
    into `hindcast_hourly` and `hindcast_daily`, from the coefficients of each issue
    day in `coefficients`. The scores are verify.py's business, which keeps the test
    period closed; fitting on it is allowed."""
    con.execute(
        "CREATE OR REPLACE TABLE coefficients (day DATE, point VARCHAR, model VARCHAR, "
        "variable VARCHAR, band INTEGER, hour_utc INTEGER, bias DOUBLE, n_pairs INTEGER)"
    )
    day = first - timedelta(days=LAST_BAND)
    while day <= last:
        start, end = window(day)
        con.execute(
            f"INSERT INTO coefficients SELECT $day, * FROM ({COEFFICIENTS})",
            {"day": day, "first": start, "last": end},
        )
        day += timedelta(days=1)
    scored = {"first": first, "last": last}
    con.execute(f"CREATE OR REPLACE TABLE hindcast_hourly AS {HINDCAST_HOURLY}", scored)
    con.execute(f"CREATE OR REPLACE TABLE hindcast_daily AS {HINDCAST_DAILY}", scored)
