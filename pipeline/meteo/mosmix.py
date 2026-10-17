"""DWD MOSMIX_L point forecasts for the airports, from opendata.dwd.de.

Issued at 03, 09, 15 and 21 UTC and published about 75 minutes later. DWD keeps
the last two days only, and nothing older can be fetched again. Each run reads
the directory listing and archives every issue still missing, so a few failed
runs leave no hole as long as one succeeds within those two days.
"""

import io
import logging
import re
import time
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import requests

from meteo.store import Store, raw_name

log = logging.getLogger(__name__)

BASE = "https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations"
NS = {
    "kml": "http://www.opengis.net/kml/2.2",
    "dwd": "https://opendata.dwd.de/weather/lib/pointforecast_dwd_extension_V1_0.xsd",
}
KELVIN = 273.15

# Element: column, scale, offset. Temperatures come in K and pressure in Pa.
# TX is valid on 18 UTC steps only, TN on 06 UTC steps, RR6c and R610 on
# 00/06/12/18, RRdc on 06, Rd10 on 00 and 06; elsewhere DWD sends "-".
ELEMENTS = {
    "TTT": ("t_c", 1.0, -KELVIN),
    "Td": ("td_c", 1.0, -KELVIN),
    "TX": ("tx_c", 1.0, -KELVIN),
    "TN": ("tn_c", 1.0, -KELVIN),
    "RR1c": ("rr1c", 1.0, 0.0),
    "RR6c": ("rr6c", 1.0, 0.0),
    "RRdc": ("rrdc", 1.0, 0.0),
    "R101": ("r101", 1.0, 0.0),
    "R610": ("r610", 1.0, 0.0),
    "Rd10": ("rd10", 1.0, 0.0),
    "FF": ("ff", 1.0, 0.0),
    "FX1": ("fx1", 1.0, 0.0),
    "DD": ("dd", 1.0, 0.0),
    "N": ("n", 1.0, 0.0),
    "VV": ("vv", 1.0, 0.0),
    "ww": ("ww", 1.0, 0.0),
    "PPPP": ("pppp_hpa", 0.01, 0.0),
}


def issues(http: requests.Session, wmo: int) -> list[datetime]:
    response = http.get(f"{BASE}/{wmo}/kml/", timeout=(5, 30))
    response.raise_for_status()
    stamps = set(re.findall(rf'href="MOSMIX_L_(\d{{10}})_{wmo}\.kmz"', response.text))
    return sorted(datetime.strptime(s, "%Y%m%d%H").replace(tzinfo=UTC) for s in stamps)


def collect(
    lake: Store,
    http: requests.Session,
    wmos: list[int],
    deadline: float,
    newest: dict[str, datetime],
) -> None:
    for wmo in wmos:
        for issue in issues(http, wmo):
            name = raw_name("mosmix", issue, str(wmo), "kmz")
            if not lake.exists("raw", name):
                if time.monotonic() > deadline:
                    log.warning("mosmix: deadline reached before %s %s", wmo, issue)
                    return
                url = f"{BASE}/{wmo}/kml/MOSMIX_L_{issue:%Y%m%d%H}_{wmo}.kmz"
                response = http.get(url, timeout=(5, 60))
                response.raise_for_status()
                metadata = {"issue_time": issue.isoformat()}
                kmz = "application/vnd.google-earth.kmz"
                lake.put_new("raw", name, response.content, kmz, metadata)
                log.info("mosmix: stored %s issue %s", wmo, issue)
            newest[str(wmo)] = issue


def rows(raw: bytes) -> Iterator[dict]:
    with zipfile.ZipFile(io.BytesIO(raw)) as kmz:
        (member,) = kmz.namelist()
        root = ET.fromstring(kmz.read(member))
    issue = datetime.fromisoformat(root.findtext(".//dwd:IssueTime", "", NS)).astimezone(UTC)
    steps = [datetime.fromisoformat(s.text or "") for s in root.iterfind(".//dwd:TimeStep", NS)]
    for placemark in root.iterfind(".//kml:Placemark", NS):
        table: dict[datetime, dict[str, float | None]] = {t: {} for t in steps}
        for forecast in placemark.iterfind(".//dwd:Forecast", NS):
            element = forecast.get(f"{{{NS['dwd']}}}elementName")
            if element not in ELEMENTS:
                continue
            column, scale, offset = ELEMENTS[element]
            values = forecast.findtext("dwd:value", "", NS).split()
            for valid, value in zip(steps, values, strict=True):
                table[valid][column] = None if value == "-" else float(value) * scale + offset
        wmo = int(placemark.findtext("kml:name", "", NS))
        for valid, columns in table.items():
            yield {
                "wmo": wmo,
                "issue": issue,
                "valid": valid,
                "lead_h": (valid - issue) // timedelta(hours=1),
                **columns,
            }
