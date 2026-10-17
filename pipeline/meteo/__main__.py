r"""Runs one job by hand, against a local folder or the real lake.

    uv run python -m meteo radar --folder ../../meteo-dati/dryrun
    uv run python -m meteo nightly --folder ../../meteo-dati/dryrun --today 2026-10-18
    uv run python -m meteo compact --day 2026-10-14 \
        --lake stkaystackmeteolakeprod --public stkaystackmeteopubprod
    uv run python -m meteo radar --day 2026-10-14 --lake stkaystackmeteolakeprod
    uv run python -m meteo check --from 2026-10-20 --to 2026-10-26 --lake stkaystackmeteolakeprod

`radar --day` fetches the frames of a past day that the lake lacks. `check` is the
"7 complete days" check: one line per day and source, exit status 1 on any FAIL.
The folder holds one subfolder per container. With --lake the job signs in with
the az CLI login; the timer jobs also need --public.
"""

import argparse
import logging
import os
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path

from meteo import check, jobs, towns
from meteo.store import AzureStore, FolderStore, Store

TIMER_JOBS = {"radar", "metar", "arpa", "hourly", "nightly"}


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m meteo")
    parser.add_argument("job", choices=[*sorted(TIMER_JOBS), "compact", "check"])
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--folder", type=Path)
    where.add_argument("--lake", help="lake storage account name")
    parser.add_argument("--public", help="public storage account name, with --lake")
    parser.add_argument("--today", type=date.fromisoformat, default=datetime.now(UTC).date())
    parser.add_argument("--day", type=date.fromisoformat, help="the day to compact or repair")
    parser.add_argument("--from", dest="first", type=date.fromisoformat)
    parser.add_argument("--to", dest="last", type=date.fromisoformat)
    parser.add_argument("--towns", type=Path, default=Path(__file__).resolve().parents[2] / "towns")
    args = parser.parse_args()
    repairing = args.job == "radar" and args.day
    if args.lake and not args.public and args.job in TIMER_JOBS and not repairing:
        parser.error(f"{args.job} needs --public with --lake")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("azure").setLevel(logging.WARNING)
    lake: Store
    public: Store
    if args.folder:
        lake = public = FolderStore(args.folder)
    else:
        from azure.identity import AzureCliCredential

        credential = AzureCliCredential()
        lake = AzureStore(args.lake, credential)
        public = AzureStore(args.public, credential) if args.public else lake

    env = os.environ
    match args.job:
        case "radar" if args.day:
            jobs.radar_repair(lake, env, args.day, minutes=60)
        case "radar":
            jobs.radar_frames(lake, public, env, minutes=4)
        case "metar":
            jobs.metar_reports(lake, public, env, args.towns)
        case "arpa":
            jobs.arpa_stations(lake, public, env, args.towns)
        case "hourly":
            jobs.hourly_forecasts(lake, public, env, args.towns, minutes=12)
        case "nightly":
            jobs.nightly(lake, public, env, args.towns, minutes=13, today=args.today)
        case "compact":
            deadline = time.monotonic() + 3600
            jobs.compact_day(lake, towns.load(args.towns), args.day, deadline, args.today)
        case "check":
            if not check.run(lake, env, towns.load(args.towns), args.first, args.last):
                sys.exit(1)


if __name__ == "__main__":
    main()
