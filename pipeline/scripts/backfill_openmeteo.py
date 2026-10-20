r"""Downloads past Open-Meteo forecasts at the forecast points into a local folder, for
the 60-day correction and its verification. It runs from the PC: the Function shares
its IP and its daily limit with the live fetches.

Single Runs gives whole runs with their start time, ECMWF IFS from 2024-03-14 and the
other models from 2026-04-02. Previous Runs gives, for each valid hour, the value
forecast k days before it, k from 0 to 7, from January 2024 for most models. Both are
asked for the station coordinates and heights, like the live fetch.

    export USER_AGENT="weather.kaystack.dev github.com/KarimElAtfy/kaystack-weather"
    uv run python -m scripts.backfill_openmeteo single --model ecmwf_ifs --hours 0,12 \
        --start 2024-03-14 --end 2024-03-20 --folder ../../meteo-dati/backfill
    uv run python -m scripts.backfill_openmeteo previous \
        --start 2024-01-20 --end 2024-02-16 --folder ../../meteo-dati/backfill
    uv run python -m scripts.backfill_openmeteo build \
        --start 2024-03-14 --end 2024-03-20 --folder ../../meteo-dati/backfill

Raw answers go to raw/backfill/ in the folder, one per run, or per model and two
weeks. A name that is already there is not asked again, so a stopped download goes
on where it was, and a run Open-Meteo does not have is remembered as missing.

Open-Meteo counts a request for more than 10 variables or more than 2 weeks as
several calls. The pricing page says nothing about several locations in one request,
so each one is counted as a call here. The calls of the UTC day are kept in
calls.json in the folder, and the download stops at --budget.

`build` writes curated/nwp_prev/ in the folder, one Parquet file per UTC day of valid
time: Previous Runs values with their day k, and Single Runs values with their run
start, their lead and day k = lead // 24.
"""

import argparse
import gzip
import json
import os
import tempfile
import time
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import requests

from meteo import compact, openmeteo, towns, web
from meteo.store import FolderStore, day_prefix, raw_name

TOWNS = Path(__file__).resolve().parents[2] / "towns"
SINGLE = "https://single-runs-api.open-meteo.com/v1/forecast"
PREVIOUS = "https://previous-runs-api.open-meteo.com/v1/forecast"
SINGLE_SOURCE = "backfill/single-runs"
PREVIOUS_SOURCE = "backfill/previous-runs"

# 12 days cover day 10 of an issue made from the run and still count as one call. A
# run ends where its model does (IFS 240 h), and the hours past it come back null.
RUN_HOURS = 288

# Two-week requests on a grid from the first day, so a chunk keeps its name.
GRID = date(2024, 1, 20)
CHUNK_DAYS = 14

# Where each model starts in Previous Runs, to the month, and its last day k with
# values, as read at Torre Boldone on 2026-10-20. ICON-CH1 has none.
PREVIOUS_MODELS = {
    "ecmwf_ifs": (date(2025, 10, 1), 7),
    "ecmwf_aifs025_single": (date(2025, 3, 1), 7),
    "icon_d2": (GRID, 1),
    "icon_eu": (GRID, 4),
    "italia_meteo_arpae_icon_2i": (date(2025, 5, 1), 2),
    "meteoswiss_icon_ch2": (date(2025, 7, 1), 4),
    "meteofrance_arome_france_hd": (GRID, 1),
    "ukmo_global_deterministic_10km": (date(2024, 10, 1), 6),
    "gfs_global": (GRID, 7),
}
# Kept to day 7 for the regressions of M4; the rest to day 2.
LONG = {"temperature_2m", "dew_point_2m", "precipitation"}

# Half of the free tier's 600 a minute.
PER_MINUTE = 300.0

TS = "TIMESTAMPTZ"
COLUMNS = {
    "point": "VARCHAR",
    "model": "VARCHAR",
    "source": "VARCHAR",
    "run_init": TS,
    "fetched_at": TS,
    "valid": TS,
    "lead_h": "SMALLINT",
    "day_offset": "SMALLINT",
    **{v: "FLOAT" for v in openmeteo.VARIABLES},
}


def weight(variables: int, hours: int, points: int) -> float:
    return points * max(1.0, variables / 10) * max(1.0, hours / (14 * 24))


class Budget:
    def __init__(self, folder: Path, limit: float, per_minute: float = PER_MINUTE) -> None:
        self.path = folder / "calls.json"
        self.limit = limit
        self.per_minute = per_minute

    def spend(self, calls: float) -> bool:
        """False, and nothing counted, when the calls would go over the day's limit."""
        spent = json.loads(self.path.read_text()) if self.path.is_file() else {}
        today = datetime.now(UTC).date().isoformat()
        if spent.get(today, 0) + calls > self.limit:
            return False
        spent[today] = round(spent.get(today, 0) + calls, 1)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(spent, indent=1, sort_keys=True))
        time.sleep(calls * 60 / self.per_minute)
        return True


def previous_variables(model: str) -> list[str]:
    # Day 0 is the plain name: Open-Meteo answers `_previous_day0` under it.
    last = PREVIOUS_MODELS[model][1]
    names = []
    for v in openmeteo.VARIABLES:
        top = last if v in LONG else min(last, 2)
        names += [v, *(f"{v}_previous_day{k}" for k in range(1, top + 1))]
    return names


def _params(points: list[towns.Station], variables: list[str], model: str) -> dict[str, str]:
    # The live fetch's own parameters, so both are asked for the same coordinates,
    # heights and units.
    params = openmeteo._params(points, variables, model)
    del params["past_hours"], params["forecast_hours"]
    return params


def _store(lake: FolderStore, name: str, response: requests.Response, metadata: dict) -> None:
    metadata = metadata | {
        "request": response.url,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    data = gzip.compress(response.content, mtime=0)
    lake.put_new("raw", name, data, "application/gzip", metadata)


def single_runs(
    lake: FolderStore,
    http: requests.Session,
    budget: Budget,
    points: list[towns.Station],
    model: str,
    runs: list[datetime],
) -> bool:
    """False when the budget ran out."""
    for run in runs:
        name = raw_name(SINGLE_SOURCE, run, model, "json.gz")
        missing = raw_name(SINGLE_SOURCE, run, model, "missing.json")
        if lake.exists("raw", name) or lake.exists("raw", missing):
            continue
        if not budget.spend(weight(len(openmeteo.VARIABLES), RUN_HOURS, len(points))):
            return False
        params = _params(points, openmeteo.VARIABLES, model) | {
            "run": f"{run:%Y-%m-%dT%H:%M}",
            "forecast_hours": str(RUN_HOURS),
        }
        response = http.get(SINGLE, params=params, timeout=(5, 60))
        if response.status_code == 400 and "not available" in response.text:
            lake.put_new("raw", missing, response.content, "application/json")
            print(model, run, "not available")
            continue
        response.raise_for_status()
        _store(lake, name, response, {"run_init": run.isoformat(), "points": _ids(points)})
        print(model, run, "stored")
    return True


def chunks(start: date, end: date) -> Iterator[tuple[date, date]]:
    first = GRID + timedelta(days=(start - GRID).days // CHUNK_DAYS * CHUNK_DAYS)
    while first <= end:
        yield first, min(first + timedelta(days=CHUNK_DAYS - 1), end)
        first += timedelta(days=CHUNK_DAYS)


def previous_runs(
    lake: FolderStore,
    http: requests.Session,
    budget: Budget,
    points: list[towns.Station],
    models: list[str],
    start: date,
    end: date,
) -> bool:
    """False when the budget ran out. A chunk cut short by `end` keeps its last day in
    its name, so asking for more later fetches the whole chunk again."""
    for first, last in chunks(start, end):
        for model in models:
            if last < PREVIOUS_MODELS[model][0]:
                continue
            when = datetime(first.year, first.month, first.day, tzinfo=UTC)
            name = raw_name(PREVIOUS_SOURCE, when, f"{model}-{last:%Y%m%d}", "json.gz")
            if lake.exists("raw", name):
                continue
            variables = previous_variables(model)
            hours = ((last - first).days + 1) * 24
            if not budget.spend(weight(len(variables), hours, len(points))):
                return False
            params = _params(points, variables, model) | {
                "start_date": first.isoformat(),
                "end_date": last.isoformat(),
            }
            response = http.get(PREVIOUS, params=params, timeout=(5, 120))
            response.raise_for_status()
            _store(lake, name, response, {"points": _ids(points)})
            print(model, first, last, "stored")
    return True


def _ids(points: list[towns.Station]) -> str:
    return ",".join(p.id for p in points)


def _model(name: str) -> str:
    variant = name.rsplit("/", 1)[1].split("-", 1)[1].split(".", 1)[0]
    return variant.rsplit("-", 1)[0] if PREVIOUS_SOURCE in name else variant


def single_rows(raw: bytes, metadata: dict[str, str], model: str) -> Iterator[dict]:
    for row in openmeteo.hourly_rows(raw, metadata, model):
        if any(row[v] is not None for v in openmeteo.VARIABLES):
            del row["run_available"]
            yield row | {"source": "single-runs", "day_offset": row["lead_h"] // 24}


def previous_rows(raw: bytes, metadata: dict[str, str], model: str) -> Iterator[dict]:
    answers = openmeteo._answers(raw)
    for point, answer in zip(metadata["points"].split(","), answers, strict=True):
        block = answer["hourly"]
        times = openmeteo._hours(block)
        for k in range(8):
            columns = {
                v: block.get(v if k == 0 else f"{v}_previous_day{k}") for v in openmeteo.VARIABLES
            }
            for i, valid in enumerate(times):
                values = {v: column[i] if column else None for v, column in columns.items()}
                if any(x is not None for x in values.values()):
                    yield {
                        "point": point,
                        "model": model,
                        "source": "previous-runs",
                        "fetched_at": metadata["fetched_at"],
                        "valid": valid,
                        "day_offset": k,
                        **values,
                    }


# Previous Runs chunks may overlap when one was cut short and fetched whole later;
# the newest answer wins.
NWP_PREV_DAY = """
SELECT * EXCLUDE (n) FROM (
    SELECT *, row_number() OVER (
        PARTITION BY point, model, source, run_init, valid, day_offset ORDER BY fetched_at DESC
    ) AS n
    FROM rows WHERE CAST(valid AS DATE) = $day
)
WHERE n = 1
ORDER BY model, source, run_init, point, valid, day_offset
"""


def build(lake: FolderStore, start: date, end: date, block_days: int = 7) -> None:
    """A week of valid days at a time: the runs of the 12 days before it and the
    chunks that touch it are read for each week."""
    with tempfile.TemporaryDirectory() as folder:
        tmp = Path(folder)
        con = compact.connect(tmp)
        first = start
        while first <= end:
            last = min(first + timedelta(days=block_days - 1), end)
            compact.write_rows(tmp / "rows.jsonl", _block_rows(lake, first, last))
            con.execute(
                "CREATE OR REPLACE TABLE rows AS SELECT * FROM read_json(?, "
                f"format = 'newline_delimited', columns = {_struct(COLUMNS)})",
                [(tmp / "rows.jsonl").as_posix()],
            )
            out = (tmp / "nwp_prev.parquet").as_posix()
            for day in _days(first, last):
                con.execute(
                    f"COPY ({NWP_PREV_DAY}) TO '{out}' (FORMAT parquet, COMPRESSION zstd)",
                    {"day": day},
                )
                (n,) = con.execute(f"SELECT count(*) FROM '{out}'").fetchone()
                if n:
                    parquet = Path(out).read_bytes()
                    name = compact.curated_name("nwp_prev", day)
                    lake.put("curated", name, parquet, "application/vnd.apache.parquet")
                print(day, n, "rows")
            first = last + timedelta(days=1)


def _struct(columns: dict[str, str]) -> str:
    return "{" + ", ".join(f"'{k}': '{v}'" for k, v in columns.items()) + "}"


def _block_rows(lake: FolderStore, first: date, last: date) -> Iterator[dict]:
    day = first - timedelta(days=RUN_HOURS // 24)
    while day <= last:
        for name in lake.names("raw", day_prefix(SINGLE_SOURCE, day)):
            if name.endswith(".json.gz"):
                raw, metadata = lake.read("raw", name)
                yield from single_rows(raw, metadata, _model(name))
        day += timedelta(days=1)
    for chunk, _ in chunks(first, last):
        for name in lake.names("raw", day_prefix(PREVIOUS_SOURCE, chunk)):
            raw, metadata = lake.read("raw", name)
            yield from previous_rows(raw, metadata, _model(name))


def _days(start: date, end: date) -> Iterator[date]:
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m scripts.backfill_openmeteo")
    parser.add_argument("what", choices=["single", "previous", "build"])
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--model", action="append", help="single: required; previous: all")
    parser.add_argument("--hours", help="single: run hours such as 0,12; all the model's runs")
    parser.add_argument("--budget", type=float, default=5000, help="weighted calls a day")
    args = parser.parse_args()
    if args.what == "single" and not args.model:
        parser.error("single needs --model")

    lake = FolderStore(args.folder)
    if args.what == "build":
        build(lake, args.start, args.end)
        return

    points = towns.forecast_points(towns.load(TOWNS))
    http = web.session(os.environ["USER_AGENT"])
    budget = Budget(args.folder, args.budget)
    if args.what == "previous":
        models = args.model or list(PREVIOUS_MODELS)
        done = previous_runs(lake, http, budget, points, models, args.start, args.end)
    else:
        done = True
        for model in args.model:
            if args.hours:
                hours = [int(h) for h in args.hours.split(",")]
            else:
                meta = openmeteo.meta(http, openmeteo.HOST, openmeteo.MODELS[model])
                hours = list(range(0, 24, meta["update_interval_seconds"] // 3600))
            runs = [
                datetime(d.year, d.month, d.day, h, tzinfo=UTC)
                for d in _days(args.start, args.end)
                for h in hours
            ]
            done = done and single_runs(lake, http, budget, points, model, runs)
    if not done:
        print("the day's budget is spent; run the same command again tomorrow")


if __name__ == "__main__":
    main()
