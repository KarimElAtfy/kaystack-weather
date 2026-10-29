import json
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


def test_the_map_carries_shapes_and_leaves_the_names_to_the_site(town):
    root = ET.parse(MAPS / f"{town.slug}.svg").getroot()
    classes = {e.get("class") for e in root.iter() if e.get("class")}
    assert classes == {"map-land", "map-river", "map-water", "map-border"}
    assert not list(root.iter(f"{SVG}text"))


def test_cities_sit_inside_the_frame_in_the_order_picked(town):
    frame = basemap.Frame(town)
    cities = json.loads((MAPS / "cities.json").read_text(encoding="utf-8"))[town.slug]
    assert len(cities) >= 6
    picked = [name for name, _, _ in basemap.CITIES[town.slug]]
    assert [c["name"] for c in cities] == [n for n in picked if n in {c["name"] for c in cities}]
    for city in cities:
        assert 0 <= city["x"] <= frame.width and 0 <= city["y"] <= frame.height, city["name"]


def test_a_city_outside_the_frame_is_left_out(town):
    frame = basemap.Frame(town)
    frame.px = lambda lon, lat: (lon, lat)
    points = basemap.city_points(frame, [("Fuori", -1.0, 50.0), ("Dentro", 40.0, 30.0)])
    assert points == [{"name": "Dentro", "x": 30.0, "y": 40.0}]


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
