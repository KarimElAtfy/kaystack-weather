r"""Draws the map under and over each town's radar frames, in the frames' own pixels,
into the SVG files the site copies into each town page.

    uv run python -m scripts.basemap --natural-earth ../../meteo-dati/natural-earth-5.1.2 \
        --out ../site/src/lib/radar/maps

Land, lakes, rivers and the Swiss border come from Natural Earth 1:10m, public
domain. The GeoJSON files are fetched into the folder when they are missing, from
the v5.1.2 tag, and checked against their SHA-256. Natural Earth's places leave out
most of the towns readers look for (Brescia, Lecco, Varese), so the places are the
ones the designer picked, at their Wikidata coordinates (P625, CC0).

The site draws the rings at 10, 25 and 50 km with their labels above the top of
each ring, the town with its name, and the 10 km bar at the bottom right. City
labels keep out of all of them: each city takes the first side of its dot where
the label fits, or is left off.
"""

import argparse
import hashlib
import json
import math
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import requests

from meteo import radar, sprites, towns
from meteo.towns import Town

RELEASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson"
SOURCES = {
    "ne_10m_lakes": "2d036f53dedec578001c5c30c2959ee7d4eebc1306900fa4367c49929ec8f2d9",
    "ne_10m_lakes_europe": "b4dd9e7a5edd0d07b54768b5404d1ebe77f80b9d579c85fff65f90cf50369769",
    "ne_10m_rivers_lake_centerlines": (
        "bb854a900ecbd3b408df46d5e16e3e0f974ba55993f9d8b5c26e855273c0905a"
    ),
    "ne_10m_rivers_europe": "90712202ac46985812e90840df9acd5101599a9c649868d5bc55ee96c2fedd4c",
    "ne_10m_admin_0_boundary_lines_land": (
        "74d9c16229c095fde65943a9919e337682f044bcebccb120764f38edf3b70f4a"
    ),
}
# Name, latitude, longitude, from Wikidata on 2026-10-21.
CITIES = {
    "pedrengo": [
        ("Bergamo", 45.695, 9.67),  # Q628
        ("Milano", 45.466944, 9.19),  # Q490
        ("Brescia", 45.538889, 10.220281),  # Q6221
        ("Lecco", 45.85334, 9.39048),  # Q6237
        ("Como", 45.81025, 9.086139),  # Q1308
        ("Treviglio", 45.521389, 9.592778),  # Q101685
        ("Crema", 45.366667, 9.683333),  # Q42793
        ("Lovere", 45.8125, 10.07),  # Q101202
    ],
    "sesto-calende": [
        ("Varese", 45.816667, 8.833333),  # Q6285
        ("Novara", 45.45, 8.62),  # Q6046
        ("Lugano", 46.010278, 8.9625),  # Q7024
        ("Locarno", 46.166389, 8.799722),  # Q11935
        ("Verbania", 45.922778, 8.551944),  # Q3639
        ("Gallarate", 45.6649, 8.7914),  # Q40854
        ("Como", 45.81025, 9.086139),  # Q1308
        ("Milano", 45.466944, 9.19),  # Q490
        ("Biella", 45.566389, 8.053333),  # Q18021
        ("Domodossola", 46.116111, 8.291111),  # Q23325
    ],
}
# The site's radar.css colours the map's classes for each theme and sets labels
# at LABEL_PX. The file carries no style of its own: WebKit and Firefox read a
# style element in a file referenced by <use> without the page's tokens.
LABEL_PX = 3.6
# A generous average glyph width for the site's sans-serif, so that the estimated
# box is never smaller than the drawn label.
CHAR_EM = 0.6
DOT_R = 0.9
# Lines are kept this far past the frame, so that they leave it at the right angle.
MARGIN = 6
TOLERANCE = 0.15
RINGS_KM = (10, 25, 50)


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    right: float
    bottom: float

    def meets(self, other: "Box") -> bool:
        return (
            self.left < other.right
            and other.left < self.right
            and self.top < other.bottom
            and other.top < self.bottom
        )

    def inside(self, width: float, height: float) -> bool:
        return self.left >= 0 and self.top >= 0 and self.right <= width and self.bottom <= height


def fetch(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name, sha256 in SOURCES.items():
        path = folder / f"{name}.geojson"
        if not path.is_file():
            response = requests.get(f"{RELEASE}/{name}.geojson", timeout=(5, 120))
            response.raise_for_status()
            path.write_bytes(response.content)
        found = hashlib.sha256(path.read_bytes()).hexdigest()
        if found != sha256:
            raise ValueError(f"{path} has SHA-256 {found}, not {sha256}")


class Frame:
    """Pixels of a town's radar frame, y down from the top edge."""

    def __init__(self, town: Town) -> None:
        self.view = town.radar_view
        self.width = (self.view["east"] - self.view["west"]) // 1000
        self.height = (self.view["north"] - self.view["south"]) // 1000
        px = sprites.town_px(town)
        # The site puts the town at the centre of its cell.
        self.town = (px.x + 0.5, px.y + 0.5)

    def px(self, lon: float, lat: float) -> tuple[float, float]:
        x, y = radar.transverse_mercator(lat, lon, 42.0, 12.5)
        return (x - self.view["west"]) / 1000, (self.view["north"] - y) / 1000

    def near(self, point: tuple[float, float]) -> bool:
        x, y = point
        return -MARGIN <= x <= self.width + MARGIN and -MARGIN <= y <= self.height + MARGIN


def ring_label_boxes(frame: Frame) -> list[Box]:
    """7 x 3 px, centred above the top of each ring the site labels."""
    tx, ty = frame.town
    return [Box(tx - 3.5, ty - km - 3, tx + 3.5, ty - km) for km in RINGS_KM if ty - km > 4]


def site_boxes(frame: Frame, town_name: str) -> list[Box]:
    """What the site draws over the map, as Radar.svelte places it."""
    tx, ty = frame.town
    w, h = frame.width, frame.height
    name = 4 * CHAR_EM * len(town_name)
    return [
        *ring_label_boxes(frame),
        Box(tx - 2.6, ty - 2.6, tx + 2.6, ty + 2.6),
        Box(tx + 3.2, ty + 4.6 - 3.2, tx + 3.2 + name, ty + 4.6 + 1),
        Box(w - 17.5, h - 9.6, w - 16 + 10 + 2.5, h - 3),
    ]


def label_box(x: float, y: float, anchor: str, text: str) -> Box:
    """The box a label takes, from its anchor point and baseline as in the SVG."""
    width = LABEL_PX * CHAR_EM * len(text)
    left = {"start": x, "end": x - width, "middle": x - width / 2}[anchor]
    return Box(left, y - 0.8 * LABEL_PX, left + width, y + 0.25 * LABEL_PX)


def placements(x: float, y: float) -> Iterator[tuple[float, float, str]]:
    yield x + 1.8, y + 1.2, "start"
    yield x - 1.8, y + 1.2, "end"
    yield x, y - 1.8, "middle"
    yield x, y + 4.4, "middle"


type City = tuple[str, float, float]
type Placed = tuple[str, float, float, float, float, str]


def place_cities(frame: Frame, town_name: str, cities: Iterable[City]) -> list[Placed]:
    """(name, dot x, dot y, label x, label y, anchor) for each city that fits."""
    taken = site_boxes(frame, town_name)
    placed: list[Placed] = []
    for name, lat, lon in cities:
        x, y = frame.px(lon, lat)
        dot = Box(x - DOT_R, y - DOT_R, x + DOT_R, y + DOT_R)
        if not dot.inside(frame.width, frame.height) or any(dot.meets(b) for b in taken):
            continue
        for lx, ly, anchor in placements(x, y):
            box = label_box(lx, ly, anchor, name)
            if box.inside(frame.width, frame.height) and not any(box.meets(b) for b in taken):
                taken += [dot, box]
                placed.append((name, x, y, lx, ly, anchor))
                break
    return placed


def simplify(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Douglas-Peucker: drops the points closer than TOLERANCE to the line kept."""
    if len(points) < 3:
        return points
    (ax, ay), (bx, by) = points[0], points[-1]
    length = math.hypot(bx - ax, by - ay)

    def distance(p: tuple[float, float]) -> float:
        if length == 0:
            return math.hypot(p[0] - ax, p[1] - ay)
        return abs((bx - ax) * (ay - p[1]) - (ax - p[0]) * (by - ay)) / length

    far, index = max((distance(p), i) for i, p in enumerate(points[1:-1], 1))
    if far <= TOLERANCE:
        return [points[0], points[-1]]
    return simplify(points[: index + 1])[:-1] + simplify(points[index:])


def lines(geometry: dict) -> list[list[list[float]]]:
    kind, coordinates = geometry["type"], geometry["coordinates"]
    if kind == "LineString":
        return [coordinates]
    if kind == "MultiLineString":
        return coordinates
    if kind == "Polygon":
        return coordinates[:1]
    if kind == "MultiPolygon":
        return [polygon[0] for polygon in coordinates]
    raise ValueError(f"unexpected geometry {kind}")


def runs(frame: Frame, line: list[list[float]]) -> Iterator[list[tuple[float, float]]]:
    """The parts of a line near the frame, each with one point past it at each end."""
    points = [frame.px(lon, lat) for lon, lat, *_ in line]
    run: list[tuple[float, float]] = []
    for i, p in enumerate(points):
        if frame.near(p):
            if not run and i > 0:
                run.append(points[i - 1])
            run.append(p)
        elif run:
            run.append(p)
            yield run
            run = []
    if len(run) > 1:
        yield run


def coords(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{_n(x)},{_n(y)}" for x, y in points)


def _n(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def features(folder: Path, name: str) -> list[dict]:
    with (folder / f"{name}.geojson").open(encoding="utf-8") as f:
        return [feature for feature in json.load(f)["features"] if feature["geometry"]]


def draw(frame: Frame, folder: Path, town_name: str, cities: Iterable[City]) -> str:
    w, h = frame.width, frame.height
    under = [f'<rect class="map-land" width="{w}" height="{h}"/>']
    for source in ("ne_10m_rivers_lake_centerlines", "ne_10m_rivers_europe"):
        for feature in features(folder, source):
            # A lake's centre line runs under the lake drawn over it.
            if feature["properties"]["featurecla"] != "River":
                continue
            for line in lines(feature["geometry"]):
                for run in runs(frame, line):
                    under.append(f'<polyline class="map-river" points="{coords(simplify(run))}"/>')
    for source in ("ne_10m_lakes", "ne_10m_lakes_europe"):
        for feature in features(folder, source):
            for ring in lines(feature["geometry"]):
                points = [frame.px(lon, lat) for lon, lat, *_ in ring]
                if any(frame.near(p) for p in points):
                    lake = coords(simplify(points))
                    under.append(f'<polygon class="map-water" points="{lake}"/>')
    over = []
    for feature in features(folder, "ne_10m_admin_0_boundary_lines_land"):
        for line in lines(feature["geometry"]):
            for run in runs(frame, line):
                over.append(f'<polyline class="map-border" points="{coords(simplify(run))}"/>')
    for name, x, y, lx, ly, anchor in place_cities(frame, town_name, cities):
        over.append(f'<circle class="map-city" cx="{_n(x)}" cy="{_n(y)}" r="{DOT_R}"/>')
        over.append(
            f'<text class="map-label" x="{_n(lx)}" y="{_n(ly)}" text-anchor="{anchor}">'
            f"{name}</text>"
        )
    box = f'viewBox="0 0 {w} {h}"'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg">'
        f'<symbol id="under" {box}>{"".join(under)}</symbol>'
        f'<symbol id="over" {box}>{"".join(over)}</symbol></svg>\n'
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m scripts.basemap")
    parser.add_argument("--natural-earth", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--towns", type=Path, default=Path(__file__).resolve().parents[2] / "towns")
    args = parser.parse_args()
    fetch(args.natural_earth)
    for town in towns.load(args.towns):
        svg = draw(Frame(town), args.natural_earth, town.name, CITIES[town.slug])
        path = args.out / f"{town.slug}.svg"
        path.write_text(svg, encoding="utf-8", newline="\n")
        print(f"{path}: {len(svg.encode())} bytes")


if __name__ == "__main__":
    main()
