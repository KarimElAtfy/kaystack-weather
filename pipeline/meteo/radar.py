"""DPC radar mosaic, product SRI (surface rainfall intensity in mm/h), one frame every 5 minutes.

The frame is a 1200 x 1400 float32 GeoTIFF on a transverse Mercator grid (origin
42N 12.5E, WGS84, scale 1, 1 km cells, upper left corner at x -600000, y 650000),
-9999 where there is no data. Only a crop around the two towns is kept.
"""

import io
import logging
import math
import time
import zlib
from datetime import UTC, date, datetime, timedelta

import requests

from meteo.store import Store, day_prefix, raw_name

log = logging.getLogger(__name__)

API = "https://radar-api.protezionecivile.it"
STEP = timedelta(minutes=5)
MAX_SLOTS = 24

# Rows 57 to 406 and columns 117 to 566: y 593 to 243 km, x -483 to -33 km.
ROW0, COL0, ROWS, COLS = 57, 117, 350, 450
NODATA = 65535
ENCODING = "u16le-x10-nodata65535-r57c117-350x450-v1"


def latest_frame(http: requests.Session, origin: str) -> datetime:
    response = http.get(
        f"{API}/findLastProductByType",
        params={"type": "SRI"},
        headers={"Origin": origin},
        timeout=(5, 20),
    )
    response.raise_for_status()
    (product,) = response.json()["lastProducts"]
    return datetime.fromtimestamp(product["time"] / 1000, UTC)


def link(http: requests.Session, origin: str, frame: datetime) -> dict | None:
    """DPC's presigned download link for a frame, or None when DPC has no such frame."""
    response = http.post(
        f"{API}/downloadProduct",
        json={"productType": "SRI", "productDate": int(frame.timestamp() * 1000)},
        headers={"Origin": origin},
        timeout=(5, 20),
    )
    # A frame DPC never produced answers 500 with an S3 HeadObject error.
    if response.status_code == 500 and "S3 error" in response.text:
        return None
    response.raise_for_status()
    found = response.json()
    # The key names the frame in UTC. Checking it means a frame is never filed
    # under another frame's time.
    if found["key"] != f"SRI/{frame:%d-%m-%Y-%H-%M}.tif":
        raise ValueError(f"asked for {frame}, DPC sent {found['key']}")
    return found


def download(http: requests.Session, origin: str, frame: datetime) -> tuple[bytes, str] | None:
    """The GeoTIFF and its S3 key, or None when DPC has no such frame."""
    found = link(http, origin, frame)
    if found is None:
        return None
    # The link expires after 300 s.
    tiff = http.get(found["url"], timeout=(5, 60))
    tiff.raise_for_status()
    return tiff.content, found["key"]


def crop(tiff: bytes) -> bytes:
    """uint16 tenths of mm/h, little endian, north row first, then zlib."""
    import numpy as np
    from PIL import Image

    # Only the TIFF decoder: whatever else the bytes claim to be never reaches
    # Pillow's other parsers.
    with Image.open(io.BytesIO(tiff), formats=["TIFF"]) as image:
        if image.mode != "F" or image.size != (1200, 1400):
            raise ValueError(f"unexpected SRI grid: mode {image.mode}, size {image.size}")
        rates = np.asarray(image, dtype="<f4")[ROW0 : ROW0 + ROWS, COL0 : COL0 + COLS]
    # Scaled in float32, so 0.35 becomes exactly 3.5 and rounds to even like the
    # reference fixture.
    tenths = np.clip(np.round(rates * np.float32(10)), 0, NODATA - 1)
    cells = np.where(rates < 0, NODATA, tenths).astype("<u2")
    return zlib.compress(cells.tobytes(), 6)


def decode(raw: bytes):
    import numpy as np

    return np.frombuffer(zlib.decompress(raw), dtype="<u2").reshape(ROWS, COLS)


def _store(lake: Store, http: requests.Session, origin: str, frame: datetime) -> bool:
    """False when DPC has no such frame."""
    got = download(http, origin, frame)
    if got is None:
        return False
    tiff, key = got
    metadata = {"frame_time": frame.isoformat(), "source_key": key, "encoding": ENCODING}
    name = raw_name("radar", frame, "sri", "u16.zlib")
    lake.put_new("raw", name, crop(tiff), "application/octet-stream", metadata)
    log.info("radar: stored %s", frame)
    return True


def collect(
    lake: Store,
    http: requests.Session,
    origin: str,
    archived: datetime | None,
    deadline: float,
    newest: dict[str, datetime],
) -> None:
    """Archives every slot after the newest archived frame up to the latest listed
    one, at most 24, so a missed run or a late frame fills itself."""
    latest = latest_frame(http, origin)
    first = latest - (MAX_SLOTS - 1) * STEP
    if archived is not None:
        first = max(first, archived + STEP)
    frame = first
    while frame <= latest:
        if time.monotonic() > deadline:
            log.warning("radar: deadline reached at %s", frame)
            break
        if lake.exists("raw", raw_name("radar", frame, "sri", "u16.zlib")) or _store(
            lake, http, origin, frame
        ):
            newest["sri"] = frame
        else:
            log.warning("radar: DPC has no frame %s", frame)
        frame += STEP


def repair(
    lake: Store, http: requests.Session, origin: str, day: date, deadline: float
) -> list[datetime] | None:
    """Fetches every slot of a past day missing from the lake: frames skipped while
    DPC answered 500, or more than 24 slots back after an outage. DPC keeps frames
    for 120 days or more. Returns the slots DPC itself lacks, or None if the
    deadline came first."""
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    stored = set(lake.names("raw", day_prefix("radar", day)))
    # DPC lists a frame about 8 minutes after its time; later slots are not gaps yet.
    listed = datetime.now(UTC) - timedelta(minutes=10)
    gaps = []
    for slot in range(288):
        frame = start + slot * STEP
        if frame > listed:
            break
        if raw_name("radar", frame, "sri", "u16.zlib") in stored:
            continue
        if time.monotonic() > deadline:
            log.warning("radar: repair of %s stopped at %s", day, frame)
            return None
        if not _store(lake, http, origin, frame):
            gaps.append(frame)
    log.info("radar: %s repaired, DPC lacks %d frames", day, len(gaps))
    return gaps


# Snyder (1987), Map Projections: A Working Manual, transverse Mercator on the
# ellipsoid, equations 8-9, 8-10 and 3-21. The SRI grid uses WGS84 and k0 = 1.
WGS84 = (6378137.0, 1 / 298.257223563)


def transverse_mercator(
    lat: float,
    lon: float,
    lat0: float,
    lon0: float,
    ellipsoid: tuple[float, float] = WGS84,
    k0: float = 1.0,
) -> tuple[float, float]:
    major, flattening = ellipsoid
    e2 = flattening * (2 - flattening)
    ep2 = e2 / (1 - e2)

    def meridian(phi: float) -> float:
        return major * (
            (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * phi
            - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * phi)
            + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * phi)
            - (35 * e2**3 / 3072) * math.sin(6 * phi)
        )

    phi = math.radians(lat)
    n = major / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    t = math.tan(phi) ** 2
    c = ep2 * math.cos(phi) ** 2
    a = math.radians(lon - lon0) * math.cos(phi)
    x = (
        k0
        * n
        * (a + (1 - t + c) * a**3 / 6 + (5 - 18 * t + t * t + 72 * c - 58 * ep2) * a**5 / 120)
    )
    y = k0 * (
        meridian(phi)
        - meridian(math.radians(lat0))
        + n
        * math.tan(phi)
        * (
            a * a / 2
            + (5 - t + 9 * c + 4 * c * c) * a**4 / 24
            + (61 - 58 * t + t * t + 600 * c - 330 * ep2) * a**6 / 720
        )
    )
    return x, y


def grid_cell(lat: float, lon: float) -> tuple[int, int]:
    """Row and column on the full SRI grid."""
    x, y = transverse_mercator(lat, lon, 42.0, 12.5)
    return math.floor((650000 - y) / 1000), math.floor((x + 600000) / 1000)
