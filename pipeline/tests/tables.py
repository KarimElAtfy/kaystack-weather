"""Raw objects written the way the collectors write them, and curated tables read
back as plain rows."""

import gzip
import json
from collections.abc import Callable
from datetime import date, datetime, timedelta

import duckdb

from meteo import compact, jobs
from meteo.store import FolderStore, raw_name


def compact_on_time(lake: FolderStore, all_towns: list, day: date) -> None:
    """Compacts a day when the nightly would: two days later."""
    jobs.compact_day(lake, all_towns, day, deadline=1e12, today=day + timedelta(days=2))


def put_arpa(lake: FolderStore, fetched: datetime, records: list[dict], variant="live") -> None:
    name = raw_name("arpa", fetched, variant, "json.gz")
    lake.put_new("raw", name, gzip.compress(json.dumps(records).encode()), "application/gzip")


def put_ensemble(
    lake: FolderStore,
    run_init: datetime,
    valid: list[datetime],
    members: int,
    t2m: Callable[[int, datetime], float],
    pr: Callable[[int, datetime], float],
) -> None:
    """One point in Open-Meteo's ensemble shape: the control, then `_memberNN` columns."""
    hourly: dict[str, list] = {"time": [t.strftime("%Y-%m-%dT%H:%M") for t in valid]}
    for m in range(members):
        suffix = f"_member{m:02d}" if m else ""
        hourly[f"temperature_2m{suffix}"] = [t2m(m, t) for t in valid]
        hourly[f"precipitation{suffix}"] = [pr(m, t) for t in valid]
    body = {"utc_offset_seconds": 0, "timezone": "GMT", "hourly": hourly}
    metadata = {
        "run_init": run_init.isoformat(),
        "run_available": run_init.isoformat(),
        "fetched_at": run_init.isoformat(),
        "points": "torre-boldone",
    }
    name = raw_name("open-meteo", run_init, "ens-icon_d2_eps", "json.gz")
    data = gzip.compress(json.dumps(body).encode())
    lake.put_new("raw", name, data, "application/gzip", metadata)


def read_table(lake: FolderStore, table: str, day: date) -> list[dict]:
    """Timestamps come back as ISO strings in UTC: turning DuckDB's TIMESTAMPTZ
    into Python objects would need pytz."""
    path = lake.root / "curated" / compact.curated_name(table, day)
    if not path.is_file():
        return []
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    source = f"'{path.as_posix()}'"
    columns = [
        f'strftime("{name}", \'%Y-%m-%dT%H:%M:%SZ\') AS "{name}"'
        if kind == "TIMESTAMP WITH TIME ZONE"
        else f'"{name}"'
        for name, kind, *_ in con.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()
    ]
    cursor = con.execute(f"SELECT {', '.join(columns)} FROM {source}")
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def table_types(lake: FolderStore, table: str, day: date) -> dict[str, str]:
    path = lake.root / "curated" / compact.curated_name(table, day)
    rows = duckdb.connect().execute(f"DESCRIBE SELECT * FROM '{path.as_posix()}'").fetchall()
    return {name: kind for name, kind, *_ in rows}
