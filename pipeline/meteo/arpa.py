"""ARPA Lombardia ground stations, through the Socrata API of dati.lombardia.it.

The live dataset holds 10-minute values and reaches the API 1 to 9 hours late,
depending on the station. `data` is local standard time, UTC+1 all year with no
summer shift, and it marks the end of the 10 minutes the value covers: 10:00 is
the mean (or, for rain, the total) from 08:50 to 09:00 UTC.
"""

import gzip
import itertools
import logging
from datetime import UTC, datetime, timedelta, timezone

import requests

from meteo.store import Store, raw_name

log = logging.getLogger(__name__)

URL = "https://www.dati.lombardia.it/resource/647i-nhxk.json"
SOLAR_TIME = timezone(timedelta(hours=1))
PAGE = 50_000
# The dataset page says -9999, the data uses -999, in the live and history datasets
# alike: all 201 rows with status NA from 2026-03-16 to 2026-10-15 hold -999.
MISSING = {-9999.0, -999.0}
# How far back each pull reaches: two days covers the latency, and the nightly
# pull of 30 days catches values ARPA revises later.
LOOKBACK = {"live": timedelta(hours=48), "revision": timedelta(days=30)}


def to_utc(label: str) -> datetime:
    return datetime.fromisoformat(label).replace(tzinfo=SOLAR_TIME).astimezone(UTC)


def collect(
    lake: Store,
    http: requests.Session,
    token: str | None,
    sensors: list[int],
    variant: str,
    newest: dict[str, datetime],
) -> None:
    """The parts are sensor ids, each with the end of its newest interval."""
    fetched = datetime.now(UTC)
    since = (fetched.astimezone(SOLAR_TIME) - LOOKBACK[variant]).strftime("%Y-%m-%dT%H:%M:%S")
    ids = ",".join(f"'{s}'" for s in sensors)
    for page in itertools.count():
        response = http.get(
            URL,
            params={
                "$select": "idsensore,data,valore,idoperatore,stato",
                "$where": f"idsensore in({ids}) AND data > '{since}'",
                # The order has to be total for $offset paging to be stable.
                "$order": "data,idsensore,idoperatore",
                "$limit": str(PAGE),
                "$offset": str(page * PAGE),
            },
            # Without a token Socrata still answers, under a lower shared rate limit.
            headers={"X-App-Token": token} if token else {},
            timeout=(5, 120),
        )
        response.raise_for_status()
        rows = response.json()
        if not rows:
            if page == 0:
                log.warning("arpa: no rows at all since %s solar time", since)
            break
        suffix = f"-p{page}" if page else ""
        name = raw_name("arpa", fetched, f"{variant}{suffix}", "json.gz")
        lake.put_new("raw", name, gzip.compress(response.content, mtime=0), "application/gzip")
        for row in rows:
            end = to_utc(row["data"])
            sensor = row["idsensore"]
            newest[sensor] = max(end, newest.get(sensor, end))
        log.info("arpa: %s page %d, %d rows since %s solar time", variant, page, len(rows), since)
        if len(rows) < PAGE:
            break
