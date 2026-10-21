import io
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from conftest import fixture
from PIL import Image

from meteo import radar, sprites
from meteo.contract import Radar

FRAME = datetime(2026, 10, 15, 17, 0, tzinfo=UTC)
REFERENCE = fixture("radar/SRI_15-10-2026-17-00.crop.u16.zlib")


def site_index(rgba: np.ndarray) -> np.ndarray:
    """What the site reads back: indexOf in site/src/lib/radar/sprite.ts."""
    grey, alpha = rgba[..., 0].astype(int), rgba[..., 3]
    return np.where(alpha == 0, 0, np.minimum(8, grey * 9 // 256))


def sprite_frames(sprite: bytes, file: Radar) -> list[np.ndarray]:
    with Image.open(io.BytesIO(sprite), formats=["WEBP"]) as image:
        pixels = np.asarray(image.convert("RGBA"))
    h, w = file.frame_height_px, file.frame_width_px
    return [
        site_index(pixels[k // file.columns * h :][:h, k % file.columns * w :][:, :w])
        for k in range(len(file.frames))
    ]


def test_every_grey_reads_back_as_its_index():
    greys = [sprites.grey(i) for i in range(9)]
    assert greys == [14, 43, 71, 99, 128, 156, 184, 213, 241]
    assert [g * 9 // 256 for g in greys] == list(range(9))


@pytest.mark.parametrize(
    ("tenths", "index"),
    [(0, 0), (1, 0), (2, 1), (9, 1), (10, 2), (59, 3), (60, 4), (399, 5), (400, 6), (9999, 6)],
)
def test_a_rate_takes_the_highest_class_it_reaches(tenths, index):
    assert sprites.classes(np.array([[tenths]], dtype="<u2"))[0, 0] == index


def test_no_data_is_hatched_from_the_top_left_of_the_frame():
    cells = np.full((4, 4), radar.NODATA, dtype="<u2")
    assert sprites.classes(cells).tolist() == [
        [7, 8, 8, 8],
        [8, 8, 8, 7],
        [8, 8, 7, 8],
        [8, 7, 8, 8],
    ]


def test_the_scale_has_the_six_classes_of_v1():
    bounds = [(b.from_mm_h, b.to_mm_h) for b in sprites.SCALE]
    assert bounds == [(0.2, 1.0), (1.0, 2.0), (2.0, 6.0), (6.0, 15.0), (15.0, 40.0), (40.0, None)]


def test_the_town_sits_on_its_own_grid_cell(all_towns):
    for town in all_towns:
        rows, cols = sprites.view_cells(town)
        row, col = radar.grid_cell(town.lat, town.lon)
        px = sprites.town_px(town)
        assert (px.y, px.x) == (row - radar.ROW0 - rows.start, col - radar.COL0 - cols.start)


def test_the_sprite_holds_the_frames_cell_for_cell(all_towns):
    town = all_towns[0]
    grid = radar.decode(REFERENCE)
    times = [FRAME - timedelta(minutes=5 * k) for k in reversed(range(sprites.FRAMES))]
    frames = [(t, None if k == 3 else grid) for k, t in enumerate(times)]
    file, sprite = sprites.build(town, frames, FRAME + timedelta(minutes=7))

    decoded = sprite_frames(sprite, file)
    rows, cols = sprites.view_cells(town)
    expected = sprites.classes(grid[rows, cols])
    assert expected.max() > 0, "the reference frame should have rain in the view"
    assert all((decoded[k] == expected).all() for k in range(12) if k != 3)
    assert (decoded[3] == sprites.hatch((120, 120))).all()
    assert [f.missing for f in file.frames] == [k == 3 for k in range(12)]
    assert file.sprite == "radar-20261015T170700Z.webp"
