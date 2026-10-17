"""MET Norway Locationforecast 2.0 (the forecast behind Yr), product `complete`.

MET's terms: name the app in the User-Agent, send at most 4 decimals, do not ask
again before `Expires`, and repeat the previous `Last-Modified` in
`If-Modified-Since`. A 203 means the product is deprecated. In Italy the product
has rain amounts but no probability of rain.
"""

import gzip
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from email.utils import parsedate_to_datetime

import requests

from meteo.store import Store, raw_name
from meteo.towns import Station

log = logging.getLogger(__name__)

URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"

# Per point, the Last-Modified to repeat and the Expires to wait for. They live
# as long as the instance; after a cold start the first request goes without.
_seen: dict[str, tuple[str, datetime]] = {}


def truncate(degrees: float) -> str:
    # The terms say truncate, and f"{x:.4f}" would round. Multiplying the float
    # instead loses a digit: 45.0014 * 10000 is 450013.99999999994.
    return str(Decimal(str(degrees)).quantize(Decimal("0.0001"), rounding=ROUND_DOWN))


def collect(
    lake: Store,
    http: requests.Session,
    points: list[Station],
    deadline: float,
    newest: dict[str, datetime],
) -> None:
    """The parts are point ids, each with the `updated_at` of its newest forecast."""
    for point in points:
        if time.monotonic() > deadline:
            log.warning("yr: deadline reached before %s", point.id)
            break
        last_modified, expires = _seen.get(point.id, ("", datetime.min.replace(tzinfo=UTC)))
        if datetime.now(UTC) < expires:
            continue
        fetched = datetime.now(UTC)
        response = http.get(
            URL,
            params={
                "lat": truncate(point.lat),
                "lon": truncate(point.lon),
                "altitude": str(point.elevation_m),
            },
            headers={"If-Modified-Since": last_modified} if last_modified else {},
            timeout=(5, 30),
        )
        response.raise_for_status()
        if response.status_code == 203:
            log.warning("yr: Locationforecast answered 203, the product is deprecated")
        _seen[point.id] = (
            response.headers.get("Last-Modified", last_modified),
            parsedate_to_datetime(response.headers["Expires"]),
        )
        if response.status_code == 304:
            continue
        updated = datetime.fromisoformat(response.json()["properties"]["meta"]["updated_at"])
        name = raw_name("yr", fetched, point.id, "json.gz")
        data = gzip.compress(response.content, mtime=0)
        lake.put_new("raw", name, data, "application/gzip", {"updated_at": updated.isoformat()})
        newest[point.id] = updated
        log.info("yr: stored %s updated %s", point.id, updated)


def rows(raw: bytes, point: str, fetched_at: datetime) -> list[dict]:
    """One row per valid time. Amounts and extremes over [t, t+n h) are stored at
    t+n h, as the end of their interval, like the models and the stations."""
    feature = json.loads(gzip.decompress(raw))
    updated = datetime.fromisoformat(feature["properties"]["meta"]["updated_at"])
    by_valid: dict[datetime, dict] = {}

    def at(valid: datetime) -> dict:
        return by_valid.setdefault(
            valid, {"point": point, "updated_at": updated, "fetched_at": fetched_at, "valid": valid}
        )

    for step in feature["properties"]["timeseries"]:
        t = datetime.fromisoformat(step["time"])
        data = step["data"]
        instant = data["instant"]["details"]
        at(t).update(
            t_c=instant.get("air_temperature"),
            td_c=instant.get("dew_point_temperature"),
            rh=instant.get("relative_humidity"),
            wind_ms=instant.get("wind_speed"),
            wind_dir=instant.get("wind_from_direction"),
            cloud=instant.get("cloud_area_fraction"),
            pmsl=instant.get("air_pressure_at_sea_level"),
        )
        if hour := data.get("next_1_hours"):
            at(t + timedelta(hours=1)).update(
                pr_1h_end=hour["details"].get("precipitation_amount"),
                symbol_1h=hour["summary"].get("symbol_code"),
            )
        if six := data.get("next_6_hours"):
            at(t + timedelta(hours=6)).update(
                pr_6h=six["details"].get("precipitation_amount"),
                tmax_6h=six["details"].get("air_temperature_max"),
                tmin_6h=six["details"].get("air_temperature_min"),
            )
    return sorted(by_valid.values(), key=lambda r: r["valid"])
