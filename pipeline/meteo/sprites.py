"""The radar sprite of each town: the last hour of frames over its view, painted as
class indices (contract encoding class-grey9/1), and the radar.json that names it.

A view lies on whole kilometres of the SRI grid, so a frame is the lake's crop cut
down to the view, one cell per pixel, with no resampling.
"""

import io
import itertools
import json
import logging
import math
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from meteo import radar
from meteo.contract import Bin, Frame, Pixel, Radar, View
from meteo.store import Store, day_prefix, raw_name
from meteo.towns import Town

# numpy and Pillow load in the job, not when the host indexes the functions.
if TYPE_CHECKING:
    import numpy as np

log = logging.getLogger(__name__)

FRAMES = 12
COLUMNS = 4
KM_PER_PX = 1.0
# The lower bound of classes 1 to 6, in the crops' tenths of mm/h.
BOUNDS = (2, 10, 20, 60, 150, 400)
HATCH_LINE, HATCH_FILL = 7, 8
LICENSE = "CC BY-SA 4.0"
ATTRIBUTION = "Radar-DPC, Dipartimento della Protezione Civile"
# A page asks for radar.json again about 7 minutes after each frame, then for the
# sprite it names once the radar is near the screen. Half an hour covers a reader
# who scrolls down late, against the 10 minutes the contract promises.
KEEP = timedelta(minutes=30)
SPRITE_CACHE = "public, max-age=86400, immutable"
CONTAINER = "public"


def grey(index: int) -> int:
    """round(255 (i + 0.5) / 9), with halves rounded up as the contract reads."""
    return (255 * (2 * index + 1) + 9) // 18


# RGBA per index: 0 is fully transparent, the others an opaque grey.
PALETTE = [(0, 0, 0, 0)] + [(grey(i), grey(i), grey(i), 255) for i in range(1, 9)]
SCALE = [
    Bin(index=i + 1, from_mm_h=low / 10, to_mm_h=high / 10 if high else None)
    for i, (low, high) in enumerate(zip(BOUNDS, (*BOUNDS[1:], None), strict=True))
]


def view_cells(town: Town) -> tuple[slice, slice]:
    """Rows and columns of the town's view inside the lake's crop."""
    v = View(**town.radar_view)
    if any(edge % 1000 for edge in (v.west, v.east, v.south, v.north)):
        raise ValueError(f"{town.slug}: view {v} is not on whole kilometres")
    top = (650000 - v.north) // 1000 - radar.ROW0
    left = (v.west + 600000) // 1000 - radar.COL0
    rows = slice(top, top + (v.north - v.south) // 1000)
    cols = slice(left, left + (v.east - v.west) // 1000)
    if top < 0 or left < 0 or rows.stop > radar.ROWS or cols.stop > radar.COLS:
        raise ValueError(f"{town.slug}: view {v} reaches outside the crop")
    return rows, cols


def town_px(town: Town) -> Pixel:
    x, y = radar.transverse_mercator(town.lat, town.lon, 42.0, 12.5)
    v = town.radar_view
    return Pixel(x=math.floor((x - v["west"]) / 1000), y=math.floor((v["north"] - y) / 1000))


def classes(tenths: "np.ndarray") -> "np.ndarray":
    """Class indices of one frame: 0 below 0.2 mm/h, 1 to 6, and the hatch where
    the radar has no data."""
    import numpy as np

    index = np.searchsorted(BOUNDS, tenths, side="right").astype(np.uint8)
    return np.where(tenths == radar.NODATA, hatch(tenths.shape), index)


def hatch(shape: tuple[int, ...]) -> "np.ndarray":
    import numpy as np

    y, x = np.indices(shape)
    return np.where((x + y) % 4 == 0, HATCH_LINE, HATCH_FILL).astype(np.uint8)


def paint(frames: "list[np.ndarray]") -> bytes:
    """One lossless WebP, frames row by row, COLUMNS to a row."""
    import numpy as np
    from PIL import Image

    height, width = frames[0].shape
    rows = math.ceil(len(frames) / COLUMNS)
    sheet = np.zeros((rows * height, COLUMNS * width), dtype=np.uint8)
    for k, frame in enumerate(frames):
        top, left = k // COLUMNS * height, k % COLUMNS * width
        sheet[top : top + height, left : left + width] = frame
    out = io.BytesIO()
    rgba = np.array(PALETTE, dtype=np.uint8)[sheet]
    Image.fromarray(rgba).save(out, "WEBP", lossless=True, quality=100, method=6)
    return out.getvalue()


def sprite_name(generated: datetime) -> str:
    return f"radar-{generated:%Y%m%dT%H%M%SZ}.webp"


def build(
    town: Town, frames: "list[tuple[datetime, np.ndarray | None]]", generated: datetime
) -> tuple[Radar, bytes]:
    """radar.json and its sprite from the crops of the last hour, oldest first; None
    for a slot DPC has no frame for."""
    rows, cols = view_cells(town)
    shape = (rows.stop - rows.start, cols.stop - cols.start)
    painted = [
        classes(grid[rows, cols]) if grid is not None else hatch(shape) for _, grid in frames
    ]
    file = Radar(
        license=LICENSE,
        attribution=ATTRIBUTION,
        generated_at=generated,
        town=town.slug,
        sprite=sprite_name(generated),
        frame_width_px=shape[1],
        frame_height_px=shape[0],
        columns=COLUMNS,
        frames=[Frame(time=t, missing=grid is None) for t, grid in frames],
        view=View(**town.radar_view),
        km_per_px=KM_PER_PX,
        town_px=town_px(town),
        scale=SCALE,
    )
    return file, paint(painted)


def last_hour(lake: Store, latest: datetime) -> "list[tuple[datetime, np.ndarray | None]]":
    slots = [latest - k * radar.STEP for k in reversed(range(FRAMES))]
    days = {s.date() for s in slots}
    stored = {n for d in days for n in lake.names("raw", day_prefix("radar", d))}
    frames = []
    for slot in slots:
        name = raw_name("radar", slot, "sri", "u16.zlib")
        frames.append((slot, radar.decode(lake.read("raw", name)[0]) if name in stored else None))
    return frames


def publish(lake: Store, public: Store, towns: list[Town], latest: datetime) -> None:
    """Writes each town's sprite, then the radar.json that names it, and removes the
    sprites that were replaced more than KEEP ago. A town whose frames are the ones
    already published is left as it is."""
    frames = last_hour(lake, latest)
    now = datetime.now(UTC)
    for town in towns:
        path = Radar.path(town.slug)
        current, _ = public.read_versioned(CONTAINER, path)
        file, sprite = build(town, frames, now)
        body = file.body()
        if current and json.loads(current)["frames"] == json.loads(body)["frames"]:
            continue
        public.put(CONTAINER, f"v1/{town.slug}/{file.sprite}", sprite, "image/webp", SPRITE_CACHE)
        public.put(CONTAINER, path, body, "application/json", Radar.CACHE)
        log.info("radar: %s sprite %s, %d bytes", town.slug, file.sprite, len(sprite))
        prune(public, town.slug, now)


def prune(public: Store, slug: str, now: datetime) -> None:
    sprites = public.names(CONTAINER, f"v1/{slug}/radar-")
    for old, newer in itertools.pairwise(sprites):
        if now - sprite_time(newer) >= KEEP:
            public.delete(CONTAINER, old)


def sprite_time(name: str) -> datetime:
    stamp = name.rsplit("/", 1)[1].removeprefix("radar-").removesuffix(".webp")
    return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
