"""Nightly compaction of raw objects into one Parquet file per table and UTC day in `curated`.

A file is rebuilt whole and replaces the previous one, so a fix in this code is
applied by compacting the day again. Each source's own format is read in Python
into a JSON-lines file; DuckDB types, deduplicates and summarises it.

Observations are filed under the UTC day of their time, forecasts under the UTC
day of their run, issue or fetch. Day D is built at D+2, after ARPA's latency.
"""

import csv
import gzip
import io
import json
import logging
import sys
import tempfile
import time
import types
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from meteo import arpa, metar, mosmix, openmeteo, radar, yr
from meteo.store import Store, day_prefix, name_time
from meteo.towns import Sensor

log = logging.getLogger(__name__)

# Torre Boldone minus Bergamo Goisis, hourly temperature over 2025: +0.41 +/- 3 C.
TEMPERATURE_BUDDY_BAND = (-2.6, 3.4)
# MISSING, SOURCE_INVALID, RANGE and SPIKE: values carrying these stay in obs_arpa
# but are left out of the hourly and daily tables.
HARD_FLAGS = 1 | 2 | 4 | 8


def curated_name(table: str, day: date) -> str:
    return f"{table}/{day:%Y/%m}/{day:%Y-%m-%d}.parquet"


def completeness_name(day: date) -> str:
    return f"completeness/{day:%Y-%m-%d}.json"


def radar_gaps_name(day: date) -> str:
    return f"radar_gaps/{day:%Y-%m-%d}.json"


def days_due(lake: Store, today: date) -> list[date]:
    """Day D is built at D+2. Up to three earlier days are built again if a failed
    night left them without a completeness file."""
    due = [today - timedelta(days=2)]
    for back in (3, 4, 5):
        day = today - timedelta(days=back)
        if not lake.exists("curated", completeness_name(day)):
            due.append(day)
    return due


def run(
    lake: Store,
    day: date,
    sensors: list[Sensor],
    radar_points: dict[str, tuple[float, float]],
    radar_towns: list[tuple[float, float]],
    deadline: float,
    today: date,
) -> None:
    # The lifecycle rule deletes raw/open-meteo/ 90 days after creation. Rebuilding
    # a day that old could replace a complete table with what is left of it, and
    # its completeness file with partial counts.
    expiring = day < today - timedelta(days=85)
    with tempfile.TemporaryDirectory() as folder:
        tmp = Path(folder)
        steps: list[tuple[str, Callable[[Any], object]]] = [
            ("nwp", lambda con: _nwp(con, lake, day, tmp)),
            ("ensemble", lambda con: _ensemble(con, lake, day, tmp)),
        ]
        if expiring:
            log.warning(
                "%s is close to the Open-Meteo expiry: nwp and ensemble left as they are", day
            )
            steps = []
        steps += [
            ("arpa", lambda con: _arpa(con, lake, day, tmp, sensors)),
            ("metar", lambda con: _metar(con, lake, day, tmp)),
            ("mosmix", lambda con: _mosmix(con, lake, day, tmp)),
            ("yr", lambda con: _yr(con, lake, day, tmp)),
            ("radar", lambda con: _radar(con, lake, day, tmp, radar_points, radar_towns)),
        ]
        counts: dict[str, object] = {"day": day.isoformat()}
        for source, step in steps:
            if time.monotonic() > deadline:
                raise TimeoutError(f"compaction of {day} stopped before {source}")
            # A connection per source: the database is in memory, so the tables of
            # one source would otherwise stay there, at the limit, under the next.
            # Reading JSON goes past the limit. On a pessimistic day in Linux the day
            # peaked at 236 to 268 MB with 256 MB and two threads, and at 210 MB in
            # three runs with these, 1 or 2 s slower.
            with connect(tmp, "160MB", threads=1, lean=True) as con:
                counts[source] = step(con)
            log.info("compacted %s %s", source, day)
    if expiring:
        return
    counts["built_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    body = json.dumps(counts, indent=1, sort_keys=True).encode()
    lake.put("curated", completeness_name(day), body, "application/json")


def connect(tmp: Path, memory_limit: str = "256MB", threads: int = 2, lean: bool = False):
    # DuckDB imports __main__ on load to tell a script from a notebook, and the
    # Python 3.13 worker on Azure has none: the import fails with "initialization
    # failed". A module with a __file__ reads as a script.
    if "__main__" not in sys.modules:
        main = types.ModuleType("__main__")
        main.__file__ = __file__
        sys.modules["__main__"] = main
    import duckdb

    con = duckdb.connect()
    # DuckDB takes the machine's zone by default, and on a PC in Italy every
    # TIMESTAMPTZ would come back at +01 or +02.
    con.execute("SET TimeZone = 'UTC'")
    # Half of the 512 MB instance by default; DuckDB spills to the temporary folder
    # beyond it, and each thread keeps buffers of its own.
    con.execute(f"SET memory_limit = '{memory_limit}'")
    con.execute(f"SET threads = {threads}")
    if lean:
        # DuckDB keeps up to 128 MiB it freed for its next task; given back at once,
        # the memory of one step is not still held under the next.
        con.execute("SET allocator_flush_threshold = '0MB'")
        con.execute("SET allocator_bulk_deallocation_flush_threshold = '0MB'")
    con.execute(f"SET temp_directory = '{(tmp / 'duckdb').as_posix()}'")
    return con


def _iso(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"cannot write {type(value).__name__} to JSON")


def write_rows(path: Path, rows: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, default=_iso))
            f.write("\n")


def _load(con, table: str, path: Path, columns: dict[str, str]) -> None:
    """Makes `table` a view of the rows, kept as Parquet next to them. A table would
    hold them all in memory: the members of a day's ensembles take 90 MB there."""
    rows = path.with_suffix(".rows.parquet").as_posix()
    con.execute(
        f"COPY (SELECT * FROM read_json(?, format = 'newline_delimited', "
        f"columns = {_struct(columns)})) TO '{rows}' (FORMAT parquet)",
        [path.as_posix()],
    )
    con.execute(f"CREATE OR REPLACE VIEW {table} AS SELECT * FROM '{rows}'")


def _struct(columns: dict[str, str]) -> str:
    return "{" + ", ".join(f"'{k}': '{v}'" for k, v in columns.items()) + "}"


def _save(
    con, lake: Store, tmp: Path, table: str, day: date, query: str, params: dict | None = None
) -> int:
    out = tmp / f"{table}.parquet"
    con.execute(f"COPY ({query}) TO '{out.as_posix()}' (FORMAT parquet, COMPRESSION zstd)", params)
    (n,) = con.execute(f"SELECT count(*) FROM '{out.as_posix()}'").fetchone()
    if n:
        parquet = out.read_bytes()
        lake.put("curated", curated_name(table, day), parquet, "application/vnd.apache.parquet")
    return n


def _raw(lake: Store, source: str, days: Iterable[date]) -> list[str]:
    return [name for d in days for name in lake.names("raw", day_prefix(source, d))]


def _variant(name: str) -> str:
    return name.rsplit("/", 1)[1].split("-", 1)[1].split(".", 1)[0]


def _model_runs(lake: Store, day: date) -> list[str]:
    """The Open-Meteo runs of the day; a run Open-Meteo never had leaves a .missing.json."""
    return [n for n in _raw(lake, "open-meteo", [day]) if n.endswith(".json.gz")]


TS = "TIMESTAMPTZ"
NWP_COLUMNS = {
    "point": "VARCHAR",
    "model": "VARCHAR",
    "run_init": TS,
    "run_available": TS,
    "fetched_at": TS,
    "valid": TS,
    "lead_h": "SMALLINT",
    **{v: "FLOAT" for v in openmeteo.VARIABLES},
}


def _nwp(con, lake: Store, day: date, tmp: Path) -> dict[str, int]:
    def rows():
        for name in _model_runs(lake, day):
            model = _variant(name)
            if model in openmeteo.MODELS or model == "best_match":
                raw, metadata = lake.read("raw", name)
                yield from openmeteo.hourly_rows(raw, metadata, model)

    write_rows(tmp / "nwp.jsonl", rows())
    _load(con, "nwp", tmp / "nwp.jsonl", NWP_COLUMNS)
    _save(
        con,
        lake,
        tmp,
        "nwp_hourly",
        day,
        "SELECT * FROM nwp ORDER BY model, run_init, fetched_at, point, valid",
    )
    counted = con.execute(
        "SELECT model, count(DISTINCT coalesce(run_init, date_trunc('hour', fetched_at))) "
        "FROM nwp GROUP BY model"
    ).fetchall()
    return dict(counted)


MEMBER_COLUMNS = {
    "point": "VARCHAR",
    "model": "VARCHAR",
    "run_init": TS,
    "run_available": TS,
    "fetched_at": TS,
    "valid": TS,
    "lead_h": "SMALLINT",
    "member": "SMALLINT",
    "t2m": "DOUBLE",
    "pr": "DOUBLE",
}

ENS_HOURLY = """
SELECT point, model, run_init, any_value(run_available) AS run_available,
       any_value(fetched_at) AS fetched_at, valid, any_value(lead_h) AS lead_h,
       count(t2m)::SMALLINT AS n_members,
       avg(t2m)::FLOAT AS t2m_mean,
       stddev_samp(t2m)::FLOAT AS t2m_sd,
       quantile_cont(t2m, 0.1)::FLOAT AS t2m_p10,
       quantile_cont(t2m, 0.5)::FLOAT AS t2m_p50,
       quantile_cont(t2m, 0.9)::FLOAT AS t2m_p90,
       avg(pr)::FLOAT AS pr_mean,
       quantile_cont(pr, 0.5)::FLOAT AS pr_p50,
       quantile_cont(pr, 0.9)::FLOAT AS pr_p90,
       avg((pr >= 0.2)::INT)::FLOAT AS pr_p_ge_0_2
FROM members
GROUP BY point, model, run_init, valid
HAVING count(t2m) > 0
ORDER BY model, run_init, point, valid
"""

# Precipitation at T covers (T-1h, T] and temperature is an instant at T, so a
# window (start, end] takes the hours with start < T <= end. A window counts only
# when every member has every hour of it.
ENS_WINDOW = """
WITH m AS (
    SELECT *,
           to_timestamp(ceil(epoch(valid) / 21600) * 21600) AS block_end,
           CAST(timezone('Europe/Rome', valid - INTERVAL 1 MICROSECOND) AS DATE) AS local_day
    FROM members
),
six AS (
    SELECT point, model, run_init, member, block_end, count(pr) AS n, sum(pr) AS pr
    FROM m GROUP BY ALL
),
day AS (
    SELECT point, model, run_init, member,
           timezone('Europe/Rome', local_day::TIMESTAMP) AS start,
           timezone('Europe/Rome', (local_day + 1)::TIMESTAMP) AS "end",
           count(pr) AS n_pr, count(t2m) AS n_t, sum(pr) AS pr, max(t2m) AS tmax, min(t2m) AS tmin
    FROM m GROUP BY ALL
)
SELECT point, model, run_init, '6h_utc' AS kind, block_end - INTERVAL 6 HOUR AS start,
       block_end AS "end", count(*)::SMALLINT AS n_members,
       avg(pr)::FLOAT AS pr_mean, avg((pr >= 1.0)::INT)::FLOAT AS pr_p_ge_1,
       NULL::FLOAT AS pr_p_ge_10, NULL::FLOAT AS tmax_mean, NULL::FLOAT AS tmax_sd,
       NULL::FLOAT AS tmin_mean, NULL::FLOAT AS tmin_sd
FROM six
GROUP BY point, model, run_init, block_end
HAVING min(n) = 6
UNION ALL
SELECT point, model, run_init, 'day_local', start, "end", count(*)::SMALLINT,
       avg(pr)::FLOAT, avg((pr >= 1.0)::INT)::FLOAT, avg((pr >= 10.0)::INT)::FLOAT,
       avg(tmax)::FLOAT, stddev_samp(tmax)::FLOAT, avg(tmin)::FLOAT, stddev_samp(tmin)::FLOAT
FROM day
GROUP BY point, model, run_init, start, "end"
HAVING min(n_pr) = date_diff('hour', start, "end") AND min(n_t) = date_diff('hour', start, "end")
ORDER BY model, run_init, point, kind, start
"""


def _ensemble(con, lake: Store, day: date, tmp: Path) -> dict[str, int]:
    def rows():
        for name in _model_runs(lake, day):
            variant = _variant(name)
            if variant.startswith("ens-"):
                raw, metadata = lake.read("raw", name)
                yield from openmeteo.member_rows(raw, metadata, variant.removeprefix("ens-"))

    write_rows(tmp / "members.jsonl", rows())
    _load(con, "members", tmp / "members.jsonl", MEMBER_COLUMNS)
    _save(con, lake, tmp, "ens_hourly", day, ENS_HOURLY)
    _save(con, lake, tmp, "ens_window", day, ENS_WINDOW)
    counted = con.execute("SELECT model, count(DISTINCT run_init) FROM members GROUP BY model")
    return dict(counted.fetchall())


ARPA_COLUMNS = {
    "sensor": "INTEGER",
    "end": TS,
    "operator": "TINYINT",
    "value": "DOUBLE",
    "status": "VARCHAR",
    "pull": "VARCHAR",
    "fetched_at": TS,
}

# One row per (sensor, operator, end): the newest pull wins, and the history of
# pulls gives REVISED (32), DUPLICATE (256), first_seen and last_seen. Then the
# per-row flags: MISSING (1), SOURCE_INVALID (2), RANGE (4), SPECIAL_CODE (128).
ARPA_OBS = """
CREATE OR REPLACE TABLE obs AS
WITH per_pull AS (
    SELECT sensor, operator, "end", pull, any_value(fetched_at) AS fetched_at,
           max(value) AS value, max(status) AS status,
           count(DISTINCT coalesce(value::VARCHAR, '-') || '|' || status) > 1 AS duplicate
    FROM pulled GROUP BY ALL
),
newest AS (
    SELECT * FROM per_pull
    QUALIFY row_number() OVER (
        PARTITION BY sensor, operator, "end" ORDER BY fetched_at DESC, pull DESC
    ) = 1
),
history AS (
    SELECT sensor, operator, "end",
           count(DISTINCT coalesce(value::VARCHAR, '-') || '|' || status) > 1 AS revised,
           bool_or(duplicate) AS duplicate,
           min(fetched_at) AS first_seen, max(fetched_at) AS last_seen
    FROM per_pull GROUP BY ALL
)
SELECT n.sensor, s.station, s.variable, n.operator, n."end",
       CASE WHEN s.variable = 'wind_direction' AND n.value IN (777, 7777, 888, 8888)
            THEN NULL ELSE n.value END AS value,
       n.status,
       (CASE WHEN n.value IS NULL THEN 1 ELSE 0 END)
       | (CASE WHEN coalesce(n.status, '') NOT IN ('VA', 'VV') THEN 2 ELSE 0 END)
       | (CASE WHEN (s.variable = 'temperature' AND (n.value < -30 OR n.value > 45))
                 OR (s.variable = 'humidity' AND (n.value < 1 OR n.value > 100))
                 OR (s.variable = 'precipitation' AND (n.value < 0 OR n.value > 50))
                 OR (s.variable = 'wind_speed' AND (n.value < 0 OR n.value > 60))
               THEN 4 ELSE 0 END)
       | (CASE WHEN h.revised THEN 32 ELSE 0 END)
       | (CASE WHEN s.variable = 'wind_direction' AND n.value IN (777, 7777, 888, 8888)
               THEN 128 ELSE 0 END)
       | (CASE WHEN h.duplicate THEN 256 ELSE 0 END) AS qc,
       h.first_seen, h.last_seen
FROM newest n
JOIN history h USING (sensor, operator, "end")
JOIN sensors s ON s.id = n.sensor
"""

ARPA_GUST = """
UPDATE obs SET qc = qc | 4
FROM (SELECT sensor, "end", value AS mean FROM obs WHERE variable = 'wind_speed' AND operator = 1) m
WHERE obs.variable = 'wind_speed' AND obs.operator = 3
  AND obs.sensor = m.sensor AND obs."end" = m."end" AND obs.value < m.mean
"""

ARPA_SPIKE = """
UPDATE obs SET qc = qc | 8
FROM (
    SELECT sensor, operator, "end",
           value - lag(value) OVER w AS rise, lead(value) OVER w - value AS fall,
           "end" - lag("end") OVER w AS before, lead("end") OVER w - "end" AS after
    FROM obs
    WHERE variable = 'temperature' AND value IS NOT NULL
    WINDOW w AS (PARTITION BY sensor, operator ORDER BY "end")
) s
WHERE obs.sensor = s.sensor AND obs.operator = s.operator AND obs."end" = s."end"
  AND s.before = INTERVAL 10 MINUTE AND s.after = INTERVAL 10 MINUTE
  AND abs(s.rise) > 4 AND abs(s.fall) > 4 AND sign(s.rise) <> sign(s.fall)
"""

# 18 identical 10-minute values in a row is 3 hours. Rain sits at 0 for days and
# humidity at saturation through fog, so neither counts. Ispra's humidity sensor
# never reads above 99: 2,785 values at 99 from March to October 2026.
ARPA_FLATLINE = """
UPDATE obs SET qc = qc | 16
FROM (
    WITH steps AS (
        SELECT sensor, operator, "end",
               CASE WHEN value = lag(value) OVER w
                     AND "end" - lag("end") OVER w = INTERVAL 10 MINUTE THEN 0 ELSE 1 END AS starts
        FROM obs
        WHERE value IS NOT NULL
          AND (variable = 'temperature' OR (variable = 'humidity' AND value < 99))
        WINDOW w AS (PARTITION BY sensor, operator ORDER BY "end")
    ),
    runs AS (
        SELECT *, sum(starts) OVER (PARTITION BY sensor, operator ORDER BY "end") AS run FROM steps
    )
    SELECT sensor, operator, "end" FROM runs
    QUALIFY count(*) OVER (PARTITION BY sensor, operator, run) >= 18
) f
WHERE obs.sensor = f.sensor AND obs.operator = f.operator AND obs."end" = f."end"
"""

# Rain: over any 3 hours, the station at 0 while its buddy has 2 mm or more, or
# the reverse. Temperature: the hourly difference from the buddy outside the band
# for 3 hours in a row. The flag goes on the station's values in those hours.
# Showers can do this between gauges 6 km apart: information only, never excluded.
ARPA_BUDDY = f"""
UPDATE obs SET qc = qc | 64
FROM (
    WITH hourly AS (
        SELECT sensor, variable, to_timestamp(ceil(epoch("end") / 3600) * 3600) AS hour_end,
               sum(value) AS total, avg(value) AS mean
        FROM obs
        WHERE value IS NOT NULL AND qc & {HARD_FLAGS} = 0
          AND ((variable = 'precipitation' AND operator = 4)
               OR (variable = 'temperature' AND operator = 1))
        GROUP BY ALL
    ),
    pairs AS (
        SELECT s.buddy_of AS station_sensor, s.id AS buddy_sensor, s.variable FROM sensors s
        WHERE s.buddy_of IS NOT NULL
    ),
    joined AS (
        SELECT p.station_sensor, p.variable, st.hour_end,
               sum(st.total) OVER w AS station_3h, sum(bd.total) OVER w AS buddy_3h,
               st.mean - bd.mean AS diff
        FROM pairs p
        JOIN hourly st ON st.sensor = p.station_sensor
        JOIN hourly bd ON bd.sensor = p.buddy_sensor AND bd.hour_end = st.hour_end
        WINDOW w AS (PARTITION BY p.station_sensor ORDER BY st.hour_end
                     RANGE BETWEEN INTERVAL 2 HOUR PRECEDING AND CURRENT ROW)
    ),
    rain AS (
        SELECT station_sensor AS sensor, hour_end - INTERVAL 3 HOUR AS start, hour_end AS stop
        FROM joined
        WHERE variable = 'precipitation'
          AND ((station_3h = 0 AND buddy_3h >= 2.0) OR (buddy_3h = 0 AND station_3h >= 2.0))
    ),
    outside AS (
        SELECT station_sensor, hour_end,
               CASE WHEN diff < {TEMPERATURE_BUDDY_BAND[0]} OR diff > {TEMPERATURE_BUDDY_BAND[1]}
                    THEN 1 ELSE 0 END AS out,
               CASE WHEN hour_end - lag(hour_end) OVER h = INTERVAL 1 HOUR THEN 0 ELSE 1 END AS gap
        FROM joined WHERE variable = 'temperature'
        WINDOW h AS (PARTITION BY station_sensor ORDER BY hour_end)
    ),
    spells AS (
        SELECT *, sum(CASE WHEN out = 0 OR gap = 1 THEN 1 ELSE 0 END)
                  OVER (PARTITION BY station_sensor ORDER BY hour_end) AS spell
        FROM outside
    ),
    warm AS (
        SELECT station_sensor AS sensor, hour_end - INTERVAL 1 HOUR AS start, hour_end AS stop
        FROM spells WHERE out = 1
        QUALIFY count(*) OVER (PARTITION BY station_sensor, spell) >= 3
    )
    SELECT * FROM rain UNION ALL SELECT * FROM warm
) b
WHERE obs.sensor = b.sensor AND obs."end" > b.start AND obs."end" <= b.stop
"""

USABLE = f"value IS NOT NULL AND qc & {HARD_FLAGS} = 0"

ARPA_DAY = """
SELECT sensor, station, variable, operator, "end", value::FLOAT AS value, status,
       qc::SMALLINT AS qc, first_seen, last_seen
FROM obs WHERE "end" > $start AND "end" <= $stop
ORDER BY sensor, operator, "end"
"""

# T3 and T4 in docs/time-conventions.md: the hour ending H takes the six values
# ending H-50 min to H; the temperature "at H" is the mean ending at H. Rain counts
# only with all six.
ARPA_HOURLY = f"""
WITH o AS (
    SELECT *, to_timestamp(ceil(epoch("end") / 3600) * 3600) AS hour_end,
           variable = 'temperature' AND operator = 1 AND {USABLE} AS t_ok,
           variable = 'humidity' AND operator = 1 AND {USABLE} AS rh_ok,
           variable = 'precipitation' AND operator = 4 AND {USABLE} AS pr_ok
    FROM obs WHERE station IS NOT NULL
)
SELECT station, hour_end,
       max(value) FILTER (WHERE t_ok AND "end" = hour_end)::FLOAT AS t_at_end,
       avg(value) FILTER (WHERE t_ok)::FLOAT AS t_mean,
       max(value) FILTER (WHERE t_ok)::FLOAT AS t_max,
       min(value) FILTER (WHERE t_ok)::FLOAT AS t_min,
       max(value) FILTER (WHERE rh_ok AND "end" = hour_end)::FLOAT AS rh_at_end,
       CASE WHEN count(*) FILTER (WHERE pr_ok) = 6
            THEN sum(value) FILTER (WHERE pr_ok) END::FLOAT AS pr_1h,
       count(*) FILTER (WHERE t_ok)::TINYINT AS n_t,
       count(*) FILTER (WHERE pr_ok)::TINYINT AS n_pr,
       bit_or(qc)::SMALLINT AS qc_any
FROM o
WHERE hour_end > $start AND hour_end <= $stop
GROUP BY station, hour_end
ORDER BY station, hour_end
"""

# T12 in docs/time-conventions.md: local day D takes the values ending in
# (D 00:00, D+1 00:00] Europe/Rome, 144 of them, or 138 and 150 on the days the
# clocks change.
ARPA_DAILY = f"""
WITH o AS (
    SELECT *, CAST(timezone('Europe/Rome', "end" - INTERVAL 1 MICROSECOND) AS DATE) AS local_day,
           variable = 'temperature' AND operator = 1 AND {USABLE} AS t_ok,
           variable = 'precipitation' AND operator = 4 AND {USABLE} AS pr_ok
    FROM obs WHERE station IS NOT NULL
),
expected AS (
    SELECT date_diff('minute', timezone('Europe/Rome', $day::TIMESTAMP),
                     timezone('Europe/Rome', ($day + 1)::TIMESTAMP)) // 10 AS n
),
rain_stations AS (
    SELECT DISTINCT station FROM sensors WHERE variable = 'precipitation' AND station IS NOT NULL
)
SELECT station, local_day AS date,
       max(value) FILTER (WHERE t_ok)::FLOAT AS tmax,
       min(value) FILTER (WHERE t_ok)::FLOAT AS tmin,
       sum(value) FILTER (WHERE pr_ok)::FLOAT AS pr_day,
       count(*) FILTER (WHERE t_ok)::SMALLINT AS n_t,
       count(*) FILTER (WHERE pr_ok)::SMALLINT AS n_pr,
       count(*) FILTER (WHERE t_ok) = (SELECT n FROM expected)
       AND (station NOT IN (SELECT station FROM rain_stations)
            OR count(*) FILTER (WHERE pr_ok) = (SELECT n FROM expected)) AS complete
FROM o
WHERE local_day = $day
GROUP BY station, local_day
ORDER BY station
"""


def arpa_rows(records: Iterable[dict], pull: str, fetched_at: datetime) -> Iterable[dict]:
    for r in records:
        # Socrata leaves a null field out of the row altogether.
        value = float(r["valore"]) if r.get("valore") is not None else None
        yield {
            "sensor": int(r["idsensore"]),
            "end": arpa.to_utc(r["data"]),
            "operator": int(r["idoperatore"]),
            "value": None if value in arpa.MISSING else value,
            "status": r.get("stato"),
            "pull": pull,
            "fetched_at": fetched_at,
        }


def _arpa(con, lake: Store, day: date, tmp: Path, sensors: list[Sensor]) -> dict[str, int]:
    # Rows ending on D arrive in live pulls made from D to D+2, and the local day D
    # starts on the evening of D-1 in UTC, so pulls from D-1 are read too. The
    # nightly 30-day pulls cover D until D+31: at D+2 only the first ones exist,
    # and compacting D again later folds in what ARPA revised since.
    def rows():
        for name in _raw(lake, "arpa", [day + timedelta(days=n) for n in range(-1, 32)]):
            fetched = name_time(name)
            if "-revision" not in name and fetched.date() > day + timedelta(days=2):
                continue
            raw, _ = lake.read("raw", name)
            text = gzip.decompress(raw).decode("utf-8")
            # The one-off CSV export from dati.lombardia.it has the same columns.
            if name.endswith(".csv.gz"):
                records: Iterable[dict] = csv.DictReader(io.StringIO(text, newline=""))
            else:
                records = json.loads(text)
            yield from arpa_rows(records, name, fetched)

    write_rows(tmp / "arpa.jsonl", rows())
    build_arpa(con, tmp / "arpa.jsonl", sensors)
    return save_arpa_day(con, lake, tmp, day)


def save_arpa_day(con, lake: Store, tmp: Path, day: date) -> dict[str, int]:
    """Writes the three ARPA tables of one day from the `obs` table build_arpa made."""
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    stop = start + timedelta(days=1)
    window = {"start": start, "stop": stop}
    _save(con, lake, tmp, "obs_arpa", day, ARPA_DAY, window)
    _save(con, lake, tmp, "obs_arpa_hourly", day, ARPA_HOURLY, window)
    _save(con, lake, tmp, "obs_arpa_daily", day, ARPA_DAILY, {"day": day})
    counted = con.execute(
        'SELECT sensor, operator, count(*) FROM obs WHERE "end" > $start AND "end" <= $stop '
        "GROUP BY ALL",
        window,
    ).fetchall()
    return {f"{s}/{o}": n for s, o, n in sorted(counted)}


def build_arpa(con, rows_path: Path, sensors: list[Sensor]) -> None:
    con.execute(
        "CREATE OR REPLACE TABLE sensors "
        "(id INTEGER, variable VARCHAR, station INTEGER, buddy_of INTEGER)"
    )
    con.executemany(
        "INSERT INTO sensors VALUES (?, ?, ?, ?)",
        [(s.id, s.variable, s.station, s.buddy_of) for s in sensors],
    )
    _load(con, "pulled", rows_path, ARPA_COLUMNS)
    for statement in (ARPA_OBS, ARPA_GUST, ARPA_SPIKE, ARPA_FLATLINE, ARPA_BUDDY):
        con.execute(statement)


METAR_COLUMNS = {
    "icao": "VARCHAR",
    "obs_time": TS,
    "type": "VARCHAR",
    "temp_c": "TINYINT",
    "dewpoint_c": "TINYINT",
    "wind_dir": "SMALLINT",
    "wind_vrb": "BOOLEAN",
    "wind_kt": "SMALLINT",
    "gust_kt": "SMALLINT",
    "vis_m": "INTEGER",
    "raw": "VARCHAR",
    "receipt": TS,
    "pull": "VARCHAR",
}

# Every pull re-reads three hours, so a report comes back up to six times. Two
# different reports for one station and minute (a METAR and a SPECI, or a
# correction) are both kept and flagged DUPLICATE.
METAR_DAY = """
WITH reports AS (
    SELECT * EXCLUDE (pull) FROM metar
    QUALIFY row_number() OVER (PARTITION BY icao, obs_time, raw ORDER BY pull DESC) = 1
)
SELECT * EXCLUDE (n_same),
       ((CASE WHEN temp_c IS NULL THEN 1 ELSE 0 END)
        | (CASE WHEN temp_c < -30 OR temp_c > 45 OR dewpoint_c > temp_c + 1
                  OR wind_kt > 117 OR gust_kt < wind_kt THEN 4 ELSE 0 END)
        | (CASE WHEN wind_vrb THEN 128 ELSE 0 END)
        | (CASE WHEN n_same > 1 THEN 256 ELSE 0 END))::SMALLINT AS qc
FROM (SELECT *, count(*) OVER (PARTITION BY icao, obs_time) AS n_same FROM reports)
WHERE obs_time >= $start AND obs_time < $stop
ORDER BY icao, obs_time, raw
"""


def _metar(con, lake: Store, day: date, tmp: Path) -> dict[str, dict]:
    def rows():
        for name in _raw(lake, "metar", [day, day + timedelta(days=1)]):
            raw, _ = lake.read("raw", name)
            for row in metar.rows(raw):
                yield row | {"pull": name}

    write_rows(tmp / "metar.jsonl", rows())
    _load(con, "metar", tmp / "metar.jsonl", METAR_COLUMNS)
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    window = {"start": start, "stop": start + timedelta(days=1)}
    _save(con, lake, tmp, "obs_metar", day, METAR_DAY, window)
    # Routine reports are the METARs at :20 and :50, 48 a day per station. The
    # times of every report let the 7-day check compare with IEM's archive.
    counted = con.execute(
        "SELECT icao, count(DISTINCT obs_time) FILTER (WHERE type = 'METAR' "
        "AND minute(obs_time) IN (20, 50)), list(DISTINCT strftime(obs_time, '%H:%M')) "
        "FROM metar WHERE obs_time >= $start AND obs_time < $stop GROUP BY icao",
        window,
    ).fetchall()
    return {icao: {"routine": n, "obs_times": sorted(t)} for icao, n, t in counted}


MOSMIX_COLUMNS = {
    "wmo": "INTEGER",
    "issue": TS,
    "valid": TS,
    "lead_h": "SMALLINT",
    **{column: "FLOAT" for column, _, _ in mosmix.ELEMENTS.values()},
    "ww": "SMALLINT",
}


def _mosmix(con, lake: Store, day: date, tmp: Path) -> dict[str, int]:
    def rows():
        for name in _raw(lake, "mosmix", [day]):
            raw, _ = lake.read("raw", name)
            yield from mosmix.rows(raw)

    write_rows(tmp / "mosmix.jsonl", rows())
    _load(con, "mosmix", tmp / "mosmix.jsonl", MOSMIX_COLUMNS)
    _save(con, lake, tmp, "mosmix", day, "SELECT * FROM mosmix ORDER BY wmo, issue, valid")
    counted = con.execute("SELECT wmo, count(DISTINCT issue) FROM mosmix GROUP BY wmo").fetchall()
    return {str(w): n for w, n in counted}


YR_COLUMNS = {
    "point": "VARCHAR",
    "updated_at": TS,
    "fetched_at": TS,
    "valid": TS,
    **dict.fromkeys(
        ["t_c", "td_c", "rh", "wind_ms", "wind_dir", "cloud", "pmsl", "pr_1h_end", "pr_6h"],
        "FLOAT",
    ),
    "tmax_6h": "FLOAT",
    "tmin_6h": "FLOAT",
    "symbol_1h": "VARCHAR",
}


def _yr(con, lake: Store, day: date, tmp: Path) -> dict[str, int]:
    def rows():
        for name in _raw(lake, "yr", [day]):
            raw, _ = lake.read("raw", name)
            yield from yr.rows(raw, _variant(name), name_time(name))

    write_rows(tmp / "yr.jsonl", rows())
    _load(con, "yr", tmp / "yr.jsonl", YR_COLUMNS)
    _save(con, lake, tmp, "yr", day, "SELECT * FROM yr ORDER BY point, fetched_at, valid")
    counted = con.execute("SELECT point, count(DISTINCT fetched_at) FROM yr GROUP BY point")
    return dict(counted.fetchall())


RADAR_POINT_COLUMNS = {
    "frame": TS,
    "point": "VARCHAR",
    "row": "SMALLINT",
    "col": "SMALLINT",
    "rate_center": "FLOAT",
    "mean_3x3": "FLOAT",
    "frac_3x3_ge_0_1": "FLOAT",
    "nodata_3x3": "TINYINT",
}
RADAR_FRAME_COLUMNS = {
    "frame": TS,
    "available": "BOOLEAN",
    "nodata_frac": "FLOAT",
    "echo_frac_ge_0_5": "FLOAT",
    "gate_40km": "BOOLEAN",
    "gate_150km": "BOOLEAN",
}


def _radar(
    con,
    lake: Store,
    day: date,
    tmp: Path,
    points: dict[str, tuple[float, float]],
    towns: list[tuple[float, float]],
) -> dict[str, object]:
    import numpy as np

    cells = {p: radar.grid_cell(lat, lon) for p, (lat, lon) in points.items()}
    rows_, cols_ = np.mgrid[0 : radar.ROWS, 0 : radar.COLS]
    distance = np.full((radar.ROWS, radar.COLS), np.inf)
    for lat, lon in towns:
        row, col = radar.grid_cell(lat, lon)
        here = np.hypot(rows_ - (row - radar.ROW0), cols_ - (col - radar.COL0))
        distance = np.minimum(distance, here)
    stored = {name_time(n): n for n in _raw(lake, "radar", [day])}
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)

    point_rows, frame_rows = [], []
    for slot in range(288):
        frame = start + slot * radar.STEP
        if frame not in stored:
            frame_rows.append({"frame": frame, "available": False})
            continue
        raw, _ = lake.read("raw", stored[frame])
        grid = radar.decode(raw)
        valid = grid != radar.NODATA
        rain = np.where(valid, grid, 0)
        # A cell is 1 km2, so 50 cells at 1 mm/h or more is 50 km2.
        heavy = valid & (rain >= 10)
        frame_rows.append(
            {
                "frame": frame,
                "available": True,
                "nodata_frac": float(1 - valid.mean()),
                "echo_frac_ge_0_5": float((valid & (rain >= 5)).sum() / max(valid.sum(), 1)),
                "gate_40km": bool((heavy & (distance <= 40)).sum() >= 50),
                "gate_150km": bool((heavy & (distance <= 150)).sum() >= 50),
            }
        )
        for point, (row, col) in cells.items():
            r, c = row - radar.ROW0, col - radar.COL0
            block = grid[r - 1 : r + 2, c - 1 : c + 2]
            ok = block != radar.NODATA
            centre = int(grid[r, c])
            point_rows.append(
                {
                    "frame": frame,
                    "point": point,
                    "row": row,
                    "col": col,
                    "rate_center": None if centre == radar.NODATA else centre / 10,
                    "mean_3x3": float(block[ok].mean() / 10) if ok.any() else None,
                    "frac_3x3_ge_0_1": float((block[ok] >= 1).mean()) if ok.any() else None,
                    "nodata_3x3": int((~ok).sum()),
                }
            )
    write_rows(tmp / "radar_points.jsonl", point_rows)
    write_rows(tmp / "radar_frames.jsonl", frame_rows)
    _load(con, "radar_points", tmp / "radar_points.jsonl", RADAR_POINT_COLUMNS)
    _load(con, "radar_frames", tmp / "radar_frames.jsonl", RADAR_FRAME_COLUMNS)
    _save(con, lake, tmp, "radar_points", day, "SELECT * FROM radar_points ORDER BY frame, point")
    _save(con, lake, tmp, "radar_frames", day, "SELECT * FROM radar_frames ORDER BY frame")
    gaps = None
    if lake.exists("curated", radar_gaps_name(day)):
        gaps = json.loads(lake.read("curated", radar_gaps_name(day))[0])["source_gaps"]
    return {"frames": len(stored), "expected": 288, "source_gaps": gaps}
