"""Uploads a CSV export of the ARPA live dataset and builds the days it covers.

The first one, downloaded on 2026-10-15 (22 sensors, 2026-03-16 to 2026-10-15),
is the only copy of those days: ARPA's history datasets stop at 2026-03-01 and
the live one keeps a few months. The file goes to raw as it is, gzipped, and the
ARPA tables of every day it covers are built from it, for the town files' sensors.

    csv=../../meteo-dati/arpa/arpa-live-dal-2026-03-16-scaricato-2026-10-15.csv
    uv run python -m scripts.upload_arpa_live --csv "$csv" --folder ../../meteo-dati/dryrun
    uv run python -m scripts.upload_arpa_live --csv "$csv" --lake stkaystackmeteolakeprod

Run it from pipeline/ after `az login`. Any later CSV from the same dataset works
the same way; the first and last day of a file are partial, so files that
overlap by a day leave no partial day behind.
"""

import argparse
import csv
import gzip
import io
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from meteo import compact, towns
from meteo.store import AzureStore, FolderStore, Store, raw_name

TOWNS = Path(__file__).resolve().parents[2] / "towns"


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m scripts.upload_arpa_live")
    parser.add_argument("--csv", type=Path, required=True)
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--lake", help="lake storage account name")
    where.add_argument("--folder", type=Path, help="a local folder instead of the lake")
    args = parser.parse_args()

    lake: Store
    if args.folder:
        lake = FolderStore(args.folder)
    else:
        from azure.identity import AzureCliCredential

        lake = AzureStore(args.lake, AzureCliCredential())

    data = args.csv.read_bytes()
    # The file was written when the download finished: that is its fetch time.
    fetched = datetime.fromtimestamp(args.csv.stat().st_mtime, UTC).replace(microsecond=0)
    name = raw_name("arpa", fetched, "portal-csv", "csv.gz")
    if lake.put_new("raw", name, gzip.compress(data, mtime=0), "application/gzip"):
        print(f"stored raw/{name}")
    else:
        print(f"raw/{name} was already there")

    records = list(csv.DictReader(io.StringIO(data.decode("utf-8"), newline="")))
    sensors = towns.arpa_sensors(towns.load(TOWNS))
    with tempfile.TemporaryDirectory() as folder:
        tmp = Path(folder)
        con = compact.connect(tmp)
        rows = compact.arpa_rows(records, name, fetched)
        compact.write_rows(tmp / "arpa.jsonl", rows)
        compact.build_arpa(con, tmp / "arpa.jsonl", sensors)
        first, last = con.execute('SELECT min("end")::DATE, max("end")::DATE FROM obs').fetchone()
        day = first
        while day <= last:
            counts = compact.save_arpa_day(con, lake, tmp, day)
            print(day, sum(counts.values()), "values")
            day += timedelta(days=1)


if __name__ == "__main__":
    main()
