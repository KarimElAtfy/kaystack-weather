import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from scripts import basemap

MAPS = Path(__file__).resolve().parents[2] / "site" / "src" / "lib" / "radar" / "maps"
SVG = "{http://www.w3.org/2000/svg}"


@pytest.fixture(params=["pedrengo", "sesto-calende"])
def town(request, all_towns):
    return next(t for t in all_towns if t.slug == request.param)


def test_each_town_has_a_map_drawn_in_its_frame(town):
    root = ET.parse(MAPS / f"{town.slug}.svg").getroot()
    frame = basemap.Frame(town)
    symbols = {s.get("id"): s.get("viewBox") for s in root.iter(f"{SVG}symbol")}
    assert symbols == {
        "under": f"0 0 {frame.width} {frame.height}",
        "over": f"0 0 {frame.width} {frame.height}",
    }


def test_city_labels_keep_clear_of_what_the_site_draws(town):
    root = ET.parse(MAPS / f"{town.slug}.svg").getroot()
    frame = basemap.Frame(town)
    labels = list(root.iter(f"{SVG}text"))
    assert len(labels) >= 6
    rings = basemap.ring_label_boxes(frame)
    assert len(rings) == 3
    for label in labels:
        x, y = float(label.get("x")), float(label.get("y"))
        box = basemap.label_box(x, y, label.get("text-anchor"), label.text)
        assert box.inside(frame.width, frame.height), label.text
        assert not any(box.meets(b) for b in basemap.site_boxes(frame, town.name)), label.text


def test_a_city_under_a_ring_label_is_left_off(town):
    frame = basemap.Frame(town)
    tx, ty = frame.town
    frame.px = lambda lon, lat: (tx, ty - 11.5)
    assert basemap.place_cities(frame, town.name, [("Qui", 0.0, 0.0)]) == []


def test_a_line_keeps_one_point_past_each_edge(town):
    frame = basemap.Frame(town)
    frame.px = lambda lon, lat: (lon, lat)
    line = [[-40.0, 60.0], [-20.0, 60.0], [10.0, 60.0], [50.0, 60.0], [200.0, 60.0]]
    assert list(basemap.runs(frame, line)) == [
        [(-20.0, 60.0), (10.0, 60.0), (50.0, 60.0), (200.0, 60.0)]
    ]


def test_simplifying_drops_points_on_the_line_and_keeps_the_corners():
    points = [(0.0, 0.0), (1.0, 0.05), (2.0, 0.0), (2.0, 3.0)]
    assert basemap.simplify(points) == [(0.0, 0.0), (2.0, 0.0), (2.0, 3.0)]
