"""now.json, the latest observation at each town: the airport's METAR and the radar
at the town. The METAR job writes the first block and the radar job the second,
each from what it has just put in the lake, so the file is replaced only if the
other job did not write it since it was read.
"""

import gzip
import json
import logging
import math
import re
from datetime import UTC, datetime, timedelta

from meteo import metar
from meteo.contract import Metar, Now, RadarAtTown, Reference
from meteo.store import Store, day_prefix
from meteo.towns import Town

log = logging.getLogger(__name__)

CONTAINER = "public"
LICENSE = "CC BY-SA 4.0"
ATTRIBUTION = (
    "METAR: NOAA Aviation Weather Center. Radar: Radar-DPC, Dipartimento della Protezione Civile"
)
EARTH_KM = 6371.0088
KMH_PER_KT = 1.852
LAYERS = ["FEW", "SCT", "BKN", "OVC", "VV"]
LAYER = re.compile(r"^(FEW|SCT|BKN|OVC)(\d{3}|///)(CB|TCU|///)?$|^(VV)(\d{3}|///)$")
CLEAR = {"CAVOK", "NSC", "NCD", "SKC", "CLR"}
# What follows these is a forecast or a remark, not the sky at the time of the report.
TREND = {"NOSIG", "TEMPO", "BECMG", "RMK"}


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine, as the contract states it, to one decimal."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    h = (
        math.sin((phi2 - phi1) / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return round(2 * EARTH_KM * math.asin(math.sqrt(h)), 1)


def cloud_cover(raw_ob: str) -> str | None:
    """The most covered layer of the report, VV, or its clear-sky code."""
    found: str | None = None
    for token in raw_ob.split():
        if token in TREND:
            break
        if m := LAYER.match(token):
            layer = m.group(1) or m.group(4)
            if found not in LAYERS or LAYERS.index(layer) > LAYERS.index(found):
                found = layer
        elif token in CLEAR and found is None:
            found = token
    return found


def _kmh(knots: float | None) -> float | None:
    return None if knots is None else round(knots * KMH_PER_KT, 1)


def metar_block(report: dict, town: Town) -> Metar:
    airport = town.airport
    variable = report.get("wdir") == "VRB"
    return Metar(
        icao=report["icaoId"],
        name=airport.name,
        distance_km=distance_km(town.lat, town.lon, airport.lat, airport.lon),
        observed_at=datetime.fromtimestamp(report["obsTime"], UTC),
        temperature_c=report.get("temp"),
        dew_point_c=report.get("dewp"),
        wind_kmh=_kmh(report.get("wspd")),
        wind_dir_deg=None if variable else report.get("wdir"),
        gust_kmh=_kmh(report.get("wgst")),
        visibility_m=metar.visibility_m(report["rawOb"]),
        weather=report.get("wxString"),
        raw=report["rawOb"],
        cloud_cover=cloud_cover(report["rawOb"]),
    )


def newest_reports(lake: Store, now: datetime) -> dict[str, dict]:
    """The newest report per airport in the latest AWC pull of today or yesterday. A
    correction of the same report comes later, so the latest receipt wins."""
    for day in (now, now - timedelta(days=1)):
        pulls = lake.names("raw", day_prefix("metar", day.date()))
        if pulls:
            break
    else:
        return {}
    newest: dict[str, dict] = {}
    for report in json.loads(gzip.decompress(lake.read("raw", pulls[-1])[0])):
        key = (report["obsTime"], report.get("receiptTime") or "")
        held = newest.get(report["icaoId"])
        if held is None or key > (held["obsTime"], held.get("receiptTime") or ""):
            newest[report["icaoId"]] = report
    return newest


def _write(public: Store, town: Town, block: str, value: Metar | RadarAtTown) -> None:
    """Replaces one block, unless it holds the same observation already."""
    path = Now.path(town.slug)
    reference = town.reference
    for _ in range(5):
        body, etag = public.read_versioned(CONTAINER, path)
        current = json.loads(body) if body else {"metar": None, "radar": None}
        if current[block] == value.model_dump(mode="json"):
            return
        blocks = {"metar": current["metar"], "radar": current["radar"], block: value}
        file = Now(
            license=LICENSE,
            attribution=ATTRIBUTION,
            generated_at=datetime.now(UTC),
            town=town.slug,
            reference=Reference(
                name=reference.name,
                distance_km=distance_km(town.lat, town.lon, reference.lat, reference.lon),
            ),
            **blocks,
        )
        if public.swap(CONTAINER, path, file.body(), etag, "application/json", Now.CACHE):
            return
    raise RuntimeError(f"{path} kept changing under the {block} job")


def publish_metar(lake: Store, public: Store, towns: list[Town], now: datetime) -> None:
    reports = newest_reports(lake, now)
    for town in towns:
        report = reports.get(town.airport.icao or "")
        if report is None:
            log.warning("now: no report from %s for %s", town.airport.icao, town.slug)
            continue
        _write(public, town, "metar", metar_block(report, town))
