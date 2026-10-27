r"""Fills, once, the deterministic runs the live archive lacks, from Single Runs, into
a local folder laid out as the lake, and uploads that folder.

    export USER_AGENT="weather.kaystack.dev github.com/KarimElAtfy/kaystack-weather"
    uv run python -m scripts.backfill_runs fetch --lake stkaystackmeteolakeprod \
        --start 2026-10-17 --end 2026-10-26 --folder ../../meteo-dati/runs-backfill
    uv run python -m scripts.backfill_runs upload --folder ../../meteo-dati/runs-backfill \
        --lake stkaystackmeteolakeprod

`fetch` only reads the lake. A model's runs are its update interval apart from 00Z
of --start, as meta.json gives it; a run neither the lake nor the folder holds is
asked by its start, as the live job asks, and one Open-Meteo never had gets the
same .missing.json. Ensemble runs cannot be filled: Open-Meteo keeps none, so the
missing ones are only listed.

Before 2026-10-28 the live job fetched the newest run from the forecast endpoint,
which for gfs_global serves the 0.13 degree domain's newer run before the 0.25 one
has it: the "00Z" of 17/10, fetched at 11:47, holds the 06Z values. Every archived
gfs_global run is compared with its Single Runs temperature at Torre Boldone over
48 hours, and one that differs is fetched again as <name>.v2.json.gz, beside the
write-once original; compaction reads the .v2 copy in its place.

`upload` writes each file of the folder once, with its metadata, and leaves alone
a name the lake already has.
"""

import argparse
import os
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from meteo import openmeteo, towns, web
from meteo.store import AzureStore, FolderStore, Store, day_prefix, raw_name

TOWNS = Path(__file__).resolve().parents[2] / "towns"
# Open-Meteo allows 600 calls a minute; one request a second stays far below.
PAUSE = 1.0
COMPARED_HOURS = 48


def days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=n) for n in range((end - start).days + 1)]


def runs_of(start: date, end: date, step: timedelta) -> list[datetime]:
    run = datetime(start.year, start.month, start.day, tzinfo=UTC)
    stop = datetime(end.year, end.month, end.day, tzinfo=UTC) + timedelta(days=1)
    found = []
    while run < stop:
        found.append(run)
        run += step
    return found


def mislabelled(lake: Store, http, point: towns.Station, name: str) -> bool | None:
    """True when the archived run's temperature differs from Single Runs' by more
    than a rounding step anywhere in its first 48 hours; None when Single Runs does
    not have the run, so that it cannot be told."""
    raw, metadata = lake.read("raw", name)
    run = datetime.fromisoformat(metadata["run_init"])
    archived = {
        r["valid"]: r["temperature_2m"]
        for r in openmeteo.hourly_rows(raw, metadata, "gfs_global")
        if r["point"] == point.id and r["valid"] - run <= timedelta(hours=COMPARED_HOURS)
    }
    params = openmeteo.run_params([point], "gfs_global", run) | {"hourly": "temperature_2m"}
    answer = http.get(openmeteo.SINGLE_RUNS, params=params, timeout=(5, 60))
    if answer.status_code == 400 and "not available" in answer.text:
        return None
    answer.raise_for_status()
    hourly = answer.json()["hourly"]
    single = dict(zip(hourly["time"], hourly["temperature_2m"], strict=True))
    for t, value in archived.items():
        other = single.get(f"{t:%Y-%m-%dT%H:%M}")
        if value is not None and (other is None or abs(value - other) > 0.05):
            return True
    return False


def fetch(lake: Store, folder: FolderStore, start: date, end: date) -> None:
    http = web.session(os.environ["USER_AGENT"])
    points = towns.forecast_points(towns.load(TOWNS))
    reference = next(p for p in points if p.id == "torre-boldone")
    period = days(start, end)
    held = openmeteo.archived(lake, period)
    filled = openmeteo.archived(folder, period)
    calls = 0
    for model, domain in openmeteo.MODELS.items():
        info = openmeteo.meta(http, openmeteo.HOST, domain)
        step = timedelta(seconds=info["update_interval_seconds"])
        for run in runs_of(start, end, step):
            if run in held.get(model, {}) or run in filled.get(model, {}):
                continue
            name = raw_name("open-meteo", run, model, "json.gz")
            calls += len(points)
            time.sleep(PAUSE)
            if openmeteo.fetch_run(folder, http, points, model, run, name, {}):
                print(f"{model} {run:%Y-%m-%d %HZ} stored")
            else:
                marker = openmeteo.missing_name(run, model)
                folder.put_new("raw", marker, b"{}", "application/json")
                print(f"{model} {run:%Y-%m-%d %HZ} not at Open-Meteo")
    for name in (n for d in period for n in lake.names("raw", day_prefix("open-meteo", d))):
        if not name.endswith("-gfs_global.json.gz"):
            continue
        copy = name.removesuffix(".json.gz") + ".v2.json.gz"
        if folder.exists("raw", copy):
            continue
        calls += 1
        time.sleep(PAUSE)
        found = mislabelled(lake, http, reference, name)
        run = datetime.fromisoformat(lake.read("raw", name)[1]["run_init"])
        if found is None:
            print(f"gfs_global {run:%Y-%m-%d %HZ} archived, not in Single Runs: left as it is")
        elif found:
            calls += len(points)
            openmeteo.fetch_run(folder, http, points, "gfs_global", run, copy, {"replaces": name})
            print(f"gfs_global {run:%Y-%m-%d %HZ} differs from Single Runs, fetched again")
    for model, domain in openmeteo.ENSEMBLES.items():
        info = openmeteo.meta(http, openmeteo.ENSEMBLE_HOST, domain)
        step = timedelta(seconds=info["update_interval_seconds"])
        lost = [r for r in runs_of(start, end, step) if r not in held.get(f"ens-{model}", {})]
        if lost:
            print(f"ens-{model}: {len(lost)} runs lost:", " ".join(f"{r:%d %HZ}" for r in lost))
    print(f"about {calls} calls")


def upload(folder: FolderStore, lake: Store) -> None:
    written = skipped = 0
    for name in folder.names("raw", "open-meteo/"):
        data, metadata = folder.read("raw", name)
        kind = "application/gzip" if name.endswith(".gz") else "application/json"
        if lake.put_new("raw", name, data, kind, metadata or None):
            written += 1
        else:
            skipped += 1
    print(f"{written} written, {skipped} already in the lake")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m scripts.backfill_runs")
    parser.add_argument("step", choices=["fetch", "upload"])
    parser.add_argument("--lake", required=True, help="lake storage account name")
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 10, 17))
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    parser.add_argument("--end", type=date.fromisoformat, default=yesterday)
    args = parser.parse_args()

    from azure.identity import AzureCliCredential

    lake = AzureStore(args.lake, AzureCliCredential())
    folder = FolderStore(args.folder)
    if args.step == "fetch":
        fetch(lake, folder, args.start, args.end)
    else:
        upload(folder, lake)


if __name__ == "__main__":
    main()
