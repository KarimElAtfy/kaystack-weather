"""METARs for the airports in the town files, from the Aviation Weather Center (NOAA).

Both airports report at :20 and :50, and AWC receives a report 5 to 14 minutes
later. Asking for the last 3 hours re-reads six reports per station, so a slow
one arrives with the next run.
"""

import gzip
import json
import logging
import re
from collections.abc import Iterator
from datetime import UTC, datetime

import requests

from meteo.store import Store, raw_name

log = logging.getLogger(__name__)

URL = "https://aviationweather.gov/api/data/metar"
# The prevailing visibility in metres; 9999 means 10 km or more. AWC's `visib` is
# in statute miles and can be the string "6+", so the report itself is read.
VISIBILITY = re.compile(r"^(\d{4})(NDV)?$")


def collect(
    lake: Store, http: requests.Session, icaos: list[str], newest: dict[str, datetime]
) -> None:
    fetched = datetime.now(UTC)
    response = http.get(
        URL, params={"ids": ",".join(icaos), "format": "json", "hours": "3"}, timeout=(5, 30)
    )
    response.raise_for_status()
    # AWC answers 204 when no station has reported in the window.
    if response.status_code == 204:
        log.warning("metar: no reports in 3 hours for %s", ",".join(icaos))
        return
    reports = response.json()
    name = raw_name("metar", fetched, "awc", "json.gz")
    lake.put_new("raw", name, gzip.compress(response.content, mtime=0), "application/gzip")
    for r in reports:
        obs = datetime.fromtimestamp(r["obsTime"], UTC)
        newest[r["icaoId"]] = max(obs, newest.get(r["icaoId"], obs))
    log.info("metar: %d reports", len(reports))


def visibility_m(raw_ob: str) -> int | None:
    tokens = raw_ob.split()
    if "CAVOK" in tokens:
        return 9999
    for token in tokens[3:]:
        if m := VISIBILITY.match(token):
            return int(m.group(1))
    return None


def rows(raw: bytes) -> Iterator[dict]:
    for r in json.loads(gzip.decompress(raw)):
        vrb = r.get("wdir") == "VRB"
        yield {
            "icao": r["icaoId"],
            "obs_time": datetime.fromtimestamp(r["obsTime"], UTC),
            "type": r.get("metarType"),
            "temp_c": r.get("temp"),
            "dewpoint_c": r.get("dewp"),
            "wind_dir": None if vrb else r.get("wdir"),
            "wind_vrb": vrb,
            "wind_kt": r.get("wspd"),
            "gust_kt": r.get("wgst"),
            "vis_m": visibility_m(r["rawOb"]),
            "raw": r["rawOb"],
            "receipt": r.get("receiptTime"),
        }
