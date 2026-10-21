import functools
import hashlib
import io
import json
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest
from conftest import fixture, replaying
from PIL import Image, UnidentifiedImageError
from tables import compact_on_time, read_table

from meteo import jobs, radar
from meteo.store import raw_name

API = "https://radar-api.protezionecivile.it"
FRAME = datetime(2026, 10, 15, 17, 0, tzinfo=UTC)
EXPECTED = json.loads(fixture("radar/SRI_15-10-2026-17-00.expected.json"))
REFERENCE = fixture("radar/SRI_15-10-2026-17-00.crop.u16.zlib")


@functools.cache
def frame_tiff() -> bytes:
    """A full SRI frame rebuilt from the reference crop: float32, -9999 outside
    the crop and where the radar has no data, LZW, as DPC serves it. The real
    frame (353 KB) stays out of the repository."""
    rates = np.full((1400, 1200), -9999, dtype="<f4")
    tenths = radar.decode(REFERENCE)
    inside = np.where(tenths == radar.NODATA, -9999, tenths / np.float32(10)).astype("<f4")
    rates[radar.ROW0 : radar.ROW0 + radar.ROWS, radar.COL0 : radar.COL0 + radar.COLS] = inside
    out = io.BytesIO()
    Image.fromarray(rates).save(out, format="TIFF", compression="tiff_lzw")
    return out.getvalue()


def test_crop_matches_the_reference_encoding():
    crop = radar.crop(frame_tiff())
    assert crop == REFERENCE
    assert hashlib.sha256(crop).hexdigest() == EXPECTED["crop_sha256"]


def test_crop_opens_nothing_but_tiff():
    png = io.BytesIO()
    Image.new("L", (1200, 1400)).save(png, format="PNG")
    with pytest.raises(UnidentifiedImageError):
        radar.crop(png.getvalue())


@pytest.mark.parametrize("point", EXPECTED["points"])
def test_grid_cell_matches_the_reference_points(point):
    expected = EXPECTED["points"][point]
    lat_lon = {
        "torre-boldone": (45.7190, 9.7102),
        "ispra-jrc": (45.8060, 8.6366),
        "varano-borghi": (45.7664, 8.7123),
        "lime": (45.6689, 9.7003),
        "pedrengo": (45.6959, 9.7392),
        "sesto-calende": (45.7240, 8.6344),
    }[point]
    x, y = radar.transverse_mercator(*lat_lon, 42.0, 12.5)
    assert (x, y) == (pytest.approx(expected["x"], abs=0.1), pytest.approx(expected["y"], abs=0.1))
    assert radar.grid_cell(*lat_lon) == (expected["row"], expected["col"])


def test_projection_reproduces_snyders_worked_example():
    # Snyder's numerical example for the ellipsoid: Clarke 1866, origin 0N 75W,
    # k0 0.9996, point 40.5N 73.5W.
    clarke_1866 = (6378206.4, 1 / 294.978698214)
    x, y = radar.transverse_mercator(40.5, -73.5, 0.0, -75.0, clarke_1866, 0.9996)
    assert (x, y) == (pytest.approx(127106.5, abs=0.1), pytest.approx(4484124.4, abs=0.1))


def dpc(frames_available: set[datetime], latest: datetime):
    def download(request):
        asked = datetime.fromtimestamp(json.loads(request.body)["productDate"] / 1000, UTC)
        if asked not in frames_available:
            return 500, fixture("radar/downloadProduct-SRI-missing.json"), {}
        key = f"SRI/{asked:%d-%m-%Y-%H-%M}.tif"
        body = {"key": key, "url": f"https://s3.example/{key}", "expiresSeconds": 300}
        return 200, json.dumps(body).encode(), {}

    listed = {
        "total": 1,
        "lastProducts": [{"productType": "SRI", "time": int(latest.timestamp() * 1000)}],
    }
    routes = {
        ("GET", f"{API}/findLastProductByType"): (200, json.dumps(listed).encode(), {}),
        ("POST", f"{API}/downloadProduct"): download,
    }
    for frame in frames_available:
        url = f"https://s3.example/SRI/{frame:%d-%m-%Y-%H-%M}.tif"
        routes[("GET", url)] = (200, frame_tiff(), {})
    return replaying(routes)


def test_catch_up_fills_every_slot_after_the_newest_archived_frame(lake):
    latest = FRAME + timedelta(minutes=20)
    frames = {FRAME + timedelta(minutes=5 * i) for i in range(5)}
    http, replay = dpc(frames, latest)
    newest = {}
    radar.collect(lake, http, "https://weather.kaystack.dev", FRAME, 1e12, newest)

    stored = lake.names("raw", "radar/2026/10/15/")
    assert stored == [
        raw_name("radar", FRAME + timedelta(minutes=m), "sri", "u16.zlib") for m in (5, 10, 15, 20)
    ]
    assert newest == {"sri": latest}
    assert all(r.headers["Origin"] == "https://weather.kaystack.dev" for r in replay.sent[:2])
    _, metadata = lake.read("raw", stored[0])
    assert metadata["source_key"] == "SRI/15-10-2026-17-05.tif"
    assert metadata["encoding"] == radar.ENCODING


def test_a_frame_dpc_never_made_is_skipped(lake):
    latest = FRAME + timedelta(minutes=10)
    http, _ = dpc({FRAME, latest}, latest)
    newest = {}
    radar.collect(
        lake, http, "https://weather.kaystack.dev", FRAME - timedelta(minutes=5), 1e12, newest
    )
    assert len(lake.names("raw", "radar/")) == 2
    assert newest == {"sri": latest}


def test_without_an_archived_frame_it_goes_back_two_hours_at_most(lake):
    latest = FRAME + timedelta(hours=5)
    http, replay = dpc(set(), latest)
    radar.collect(lake, http, "https://weather.kaystack.dev", None, 1e12, {})
    asked = [json.loads(r.body)["productDate"] for r in replay.sent if r.method == "POST"]
    assert len(asked) == radar.MAX_SLOTS
    assert asked[-1] == int(latest.timestamp() * 1000)


def test_a_frame_under_another_name_is_refused(lake):
    http, _ = replaying(
        {
            ("POST", f"{API}/downloadProduct"): (
                200,
                json.dumps(
                    {"key": "SRI/15-10-2026-17-05.tif", "url": "https://s3.example/x"}
                ).encode(),
                {},
            )
        }
    )
    with pytest.raises(ValueError, match="DPC sent"):
        radar.download(http, "https://weather.kaystack.dev", FRAME)


def test_radar_tables_from_one_frame(lake, all_towns):
    name = raw_name("radar", FRAME, "sri", "u16.zlib")
    lake.put_new("raw", name, REFERENCE, "application/octet-stream")
    compact_on_time(lake, all_towns, date(2026, 10, 15))

    frames = read_table(lake, "radar_frames", date(2026, 10, 15))
    assert len(frames) == 288
    (available,) = [f for f in frames if f["available"]]
    assert available["frame"] == "2026-10-15T17:00:00Z"
    # 5,120 cells over Switzerland never have data, 3.3 % of the crop.
    assert available["nodata_frac"] == pytest.approx(5120 / (350 * 450), rel=1e-4)

    points = {p["point"]: p for p in read_table(lake, "radar_points", date(2026, 10, 15))}
    assert set(points) == set(EXPECTED["points"])
    for point, expected in EXPECTED["points"].items():
        assert (points[point]["row"], points[point]["col"]) == (expected["row"], expected["col"])
        # The reference reads the float32 TIFF; the archive keeps tenths of mm/h.
        assert points[point]["rate_center"] == pytest.approx(expected["rate_center"], abs=0.05)
        assert points[point]["mean_3x3"] == pytest.approx(expected["mean_3x3"], abs=0.05)


def test_repair_fills_a_past_day_and_names_what_dpc_lacks(lake, all_towns, monkeypatch):
    day = date(2026, 10, 15)
    start = datetime(2026, 10, 15, tzinfo=UTC)
    skipped = {FRAME, FRAME + timedelta(minutes=5), FRAME + timedelta(minutes=10)}
    for slot in range(288):
        frame = start + slot * radar.STEP
        if frame not in skipped:
            name = raw_name("radar", frame, "sri", "u16.zlib")
            lake.put_new("raw", name, REFERENCE, "application/octet-stream")
    http, _ = dpc({FRAME, FRAME + timedelta(minutes=10)}, FRAME)
    monkeypatch.setattr(jobs, "_radar_session", lambda env: http)
    env = {
        "USER_AGENT": "weather.kaystack.dev github.com/KarimElAtfy/kaystack-weather",
        "RADAR_ORIGIN": "x",
    }

    jobs.radar_repair(lake, env, day, minutes=5)
    assert len(lake.names("raw", "radar/2026/10/15/")) == 287
    compact_on_time(lake, all_towns, day)
    counts = json.loads(lake.read("curated", "completeness/2026-10-15.json")[0])
    assert counts["radar"] == {"expected": 288, "frames": 287, "source_gaps": ["17:05"]}
