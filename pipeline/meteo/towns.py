import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    lat: float
    lon: float
    elevation_m: int
    arpa_station: int | None = None
    sensors: dict[str, int] = field(default_factory=dict)
    # Neighbouring sensors kept only to cross-check the station's own.
    buddies: dict[str, int] = field(default_factory=dict)
    icao: str | None = None
    wmo: int | None = None
    benchmark: bool = False


@dataclass(frozen=True)
class Town:
    name: str
    slug: str
    lat: float
    lon: float
    reference: Station
    airport: Station
    radar_view: dict[str, int]
    inland: Station | None = None

    def forecast_points(self) -> list[Station]:
        """Where forecasts are fetched: the stations they are scored against."""
        points = [self.reference]
        if self.inland:
            points.append(self.inland)
        if self.airport.benchmark:
            points.append(self.airport)
        return points


def load(folder: Path) -> list[Town]:
    towns = []
    for path in sorted(folder.glob("*.toml")):
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        towns.append(
            Town(
                name=raw["name"],
                slug=raw["slug"],
                lat=raw["lat"],
                lon=raw["lon"],
                reference=Station(**raw["reference"]),
                airport=Station(**raw["airport"]),
                inland=Station(**raw["inland"]) if "inland" in raw else None,
                radar_view=raw["radar"]["view"],
            )
        )
    if not towns:
        raise FileNotFoundError(f"no town files in {folder}")
    return towns


def forecast_points(towns: list[Town]) -> list[Station]:
    return [p for t in towns for p in t.forecast_points()]


def airports(towns: list[Town]) -> list[Station]:
    return [t.airport for t in towns]


@dataclass(frozen=True)
class Sensor:
    id: int
    variable: str
    # None for a buddy: the town files name its sensor, not its station.
    station: int | None
    # For a buddy, the station sensor it cross-checks.
    buddy_of: int | None = None


def arpa_sensors(towns: list[Town]) -> list[Sensor]:
    found = {}
    for town in towns:
        for station in (town.reference, town.inland):
            if station is None:
                continue
            for variable, sensor in station.sensors.items():
                found[sensor] = Sensor(sensor, variable, station.arpa_station)
            for variable, sensor in station.buddies.items():
                found[sensor] = Sensor(sensor, variable, None, station.sensors[variable])
    return sorted(found.values(), key=lambda s: s.id)


def reference_sensors(towns: list[Town]) -> list[int]:
    return sorted(s for t in towns for s in t.reference.sensors.values())
