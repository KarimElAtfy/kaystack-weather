r"""Draws the map under and over each town's radar frames, in the frames' own pixels,
into the SVG files the site copies into each town page, and writes where the
cities fall in those pixels.

    uv run python -m scripts.basemap --natural-earth ../../meteo-dati/natural-earth-5.1.2 \
        --out ../site/src/lib/radar/maps

Land, lakes, rivers and the Swiss border come from Natural Earth 1:10m, public
domain. The GeoJSON files are fetched into the folder when they are missing, from
the v5.1.2 tag, and checked against their SHA-256. Natural Earth's places leave out
most of the towns readers look for (Brescia, Lecco, Varese), so the places are the
ones the designer picked, at their Wikidata coordinates (P625, CC0).

The maps hold shapes only. The site writes the names in the page's own type, so
they keep their size at any map width and text setting, and leaves out the ones
that collide there; cities.json gives it each city's point, in the order the site
drops them last.
"""

import argparse
import hashlib
import json
import math
from collections.abc import Iterable, Iterator
from pathlib import Path

import requests

from meteo import radar, towns
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
# Lines are kept this far past the frame, so that they leave it at the right angle.
MARGIN = 6
TOLERANCE = 0.15


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

    def px(self, lon: float, lat: float) -> tuple[float, float]:
        x, y = radar.transverse_mercator(lat, lon, 42.0, 12.5)
        return (x - self.view["west"]) / 1000, (self.view["north"] - y) / 1000

    def near(self, point: tuple[float, float]) -> bool:
        x, y = point
        return -MARGIN <= x <= self.width + MARGIN and -MARGIN <= y <= self.height + MARGIN


type City = tuple[str, float, float]


def city_points(frame: Frame, cities: Iterable[City]) -> list[dict[str, float | str]]:
    """Each city inside the frame, as the site reads it: name and point in pixels."""
    found: list[dict[str, float | str]] = []
    for name, lat, lon in cities:
        x, y = frame.px(lon, lat)
        if 0 <= x <= frame.width and 0 <= y <= frame.height:
            found.append({"name": name, "x": round(x, 2), "y": round(y, 2)})
    return found


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


def draw(frame: Frame, folder: Path) -> str:
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
    points = {}
    for town in towns.load(args.towns):
        frame = Frame(town)
        svg = draw(frame, args.natural_earth)
        path = args.out / f"{town.slug}.svg"
        path.write_text(svg, encoding="utf-8", newline="\n")
        print(f"{path}: {len(svg.encode())} bytes")
        points[town.slug] = city_points(frame, CITIES[town.slug])
    # One city a line, as the site's formatter keeps it.
    blocks = [
        f"  {json.dumps(slug)}: [\n"
        + ",\n".join(f"    {{ {json.dumps(city, ensure_ascii=False)[1:-1]} }}" for city in cities)
        + "\n  ]"
        for slug, cities in points.items()
    ]
    text = "{\n" + ",\n".join(blocks) + "\n}\n"
    (args.out / "cities.json").write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
