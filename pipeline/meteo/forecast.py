"""forecast.json for each town's reference station, issued by the hourly job with
mean60-v1 from the newest run of each model in the lake, and the issued copy kept
in the forecasts container.

Temperature is corrected per model with the coefficients the nightly wrote for the
day of the issue (mos.py), then averaged; a model whose cell has fewer than 45 pairs
stays out of the mean there. Everything else is the plain mean of the models with a
value. A model counts for a day only with every hour of it.
"""

import logging
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from statistics import fmean

from meteo import mos, openmeteo
from meteo.contract import (
    ROME,
    Consensus,
    Daily,
    Forecast,
    Hourly,
    RainCount,
    Run,
    Spread,
)
from meteo.store import Store, day_prefix, name_time
from meteo.towns import Town

log = logging.getLogger(__name__)

LICENSE = "CC BY-SA 4.0"
ATTRIBUTION = (
    "Weather data by Open-Meteo.com (CC BY 4.0), temperature corrected against ARPA Lombardia"
)
HOURS = 49
DAYS = 10
HOUR = timedelta(hours=1)
RAIN_HOUR_MM = 0.2
RAIN_DAY_MM = 1.0
KMH_PER_MS = 3.6
# The coefficients of the day are written at 02:20 UTC, so the issues at 00:45 and
# 01:45 take the previous day's. Older than this, their timer is broken.
COEFFICIENTS_DAYS = 3
ISSUED = "forecasts"


@dataclass(frozen=True)
class ModelRun:
    model: str
    run_init: datetime
    # Point and valid time to the run's row of hourly values.
    hours: dict[tuple[str, datetime], dict]

    def value(self, point: str, valid: datetime, variable: str) -> float | None:
        row = self.hours.get((point, valid))
        return None if row is None else row[variable]


def newest_runs(lake: Store, now: datetime) -> list[ModelRun]:
    """The newest run of each deterministic model archived today or yesterday."""
    newest: dict[str, str] = {}
    for day in (now.date() - timedelta(days=1), now.date()):
        for name in lake.names("raw", day_prefix("open-meteo", day)):
            model = name.rsplit("/", 1)[1].split("-", 1)[1].removesuffix(".json.gz")
            if model not in openmeteo.MODELS or name_time(name) > now:
                continue
            if model not in newest or name_time(name) > name_time(newest[model]):
                newest[model] = name
    runs = []
    for model, name in sorted(newest.items()):
        raw, metadata = lake.read("raw", name)
        rows = openmeteo.hourly_rows(raw, metadata, model)
        hours = {(r["point"], r["valid"]): r for r in rows}
        runs.append(ModelRun(model, name_time(name), hours))
    return runs


def coefficients(lake: Store, day: date) -> mos.Coefficients | None:
    for back in range(COEFFICIENTS_DAYS + 1):
        found = day - timedelta(days=back)
        if lake.exists("curated", mos.name(found)):
            if back:
                log.info("forecast: no mean60 coefficients of %s yet, using %s", day, found)
            return mos.Coefficients.read(lake.read("curated", mos.name(found))[0])
    return None


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits) + 0.0


def _mean(values: list[float], digits: int = 1) -> float | None:
    return _round(fmean(values), digits) if values else None


def _spread(steps: list[tuple[list[float], int]]) -> Spread:
    """From the corrected values of each step and its lead band."""
    return Spread(
        corrected=True,
        mean=[_mean(v) for v, _ in steps],
        low=[_round(min(v), 1) if v else None for v, _ in steps],
        high=[_round(max(v), 1) if v else None for v, _ in steps],
        m_models=[len(v) for v, _ in steps],
        lead_band=[band for _, band in steps],
    )


def _wind_direction(winds: list[tuple[float, float]]) -> float | None:
    """The direction the mean wind vector blows from."""
    if not winds:
        return None
    u = fmean(-s * math.sin(math.radians(d)) for s, d in winds)
    v = fmean(-s * math.cos(math.radians(d)) for s, d in winds)
    if math.hypot(u, v) < 1e-6:
        return None
    return float(round(math.degrees(math.atan2(-u, -v))) % 360)


class Issue:
    """One forecast: the runs, the coefficients and the point it is made for."""

    def __init__(
        self,
        runs: list[ModelRun],
        coefficients: mos.Coefficients | None,
        point: str,
        issued: datetime,
    ) -> None:
        self.runs, self.coefficients, self.point, self.issued = runs, coefficients, point, issued
        self.used: set[str] = set()

    def values(self, valid: datetime, variable: str) -> list[tuple[ModelRun, float]]:
        found = []
        for run in self.runs:
            value = run.value(self.point, valid, variable)
            if value is not None:
                found.append((run, value))
                self.used.add(run.model)
        return found

    def correct(
        self, run: ModelRun, variable: str, band: int, hour: int | None, value: float
    ) -> float | None:
        if self.coefficients is None:
            return None
        return self.coefficients.correct(self.point, run.model, variable, band, hour, value)

    def hourly(self) -> Hourly:
        first = self.issued.replace(minute=0, second=0, microsecond=0)
        if first < self.issued:
            first += HOUR
        times = [first + k * HOUR for k in range(HOURS)]
        temperature, dew, wind, direction, gust, cloud, rain_mm, rainy, counted = (
            [] for _ in range(9)
        )
        for t in times:
            corrected, bands = [], []
            for run, value in self.values(t, "temperature_2m"):
                band = mos.hourly_band(t, run.run_init)
                fixed = self.correct(run, "t2m", band, t.hour, value)
                if fixed is not None:
                    corrected.append(fixed)
                    bands.append(band)
            ahead = min((t - self.issued) // timedelta(hours=24), mos.LAST_BAND)
            temperature.append((corrected, max(bands, default=ahead)))
            dew.append(_mean([v for _, v in self.values(t, "dew_point_2m")]))
            speeds = {r.model: v for r, v in self.values(t, "wind_speed_10m")}
            wind.append(_mean([v * KMH_PER_MS for v in speeds.values()]))
            directions = self.values(t, "wind_direction_10m")
            direction.append(
                _wind_direction([(speeds[r.model], d) for r, d in directions if r.model in speeds])
            )
            gust.append(_mean([v * KMH_PER_MS for _, v in self.values(t, "wind_gusts_10m")]))
            cloud.append(_mean([v for _, v in self.values(t, "cloud_cover")], 0))
            amounts = [v for _, v in self.values(t, "precipitation")]
            rain_mm.append(_mean(amounts))
            rainy.append(sum(a >= RAIN_HOUR_MM for a in amounts))
            counted.append(len(amounts))
        return Hourly(
            time=times,
            temperature_c=_spread(temperature),
            dew_point_c=Consensus(corrected=False, mean=dew),
            wind_kmh=Consensus(corrected=False, mean=wind),
            wind_dir_deg=Consensus(corrected=False, mean=direction),
            gust_kmh=Consensus(corrected=False, mean=gust),
            cloud_pct=Consensus(corrected=False, mean=cloud),
            precipitation_mm=Consensus(corrected=False, mean=rain_mm),
            rain=RainCount(threshold_mm=RAIN_HOUR_MM, n_models=rainy, m_models=counted),
        )

    def whole_day(self, hours: list[datetime], variable: str) -> dict[str, list[float]]:
        """Each model's values over the day, for the models that have all of them."""
        per_model: dict[str, list[float]] = {}
        for t in hours:
            for run, value in self.values(t, variable):
                per_model.setdefault(run.model, []).append(value)
        return {m: v for m, v in per_model.items() if len(v) == len(hours)}

    def daily(self) -> Daily:
        issue_day = self.issued.astimezone(ROME).date()
        days = [issue_day + timedelta(days=k) for k in range(1, DAYS + 1)]
        runs = {r.model: r for r in self.runs}
        tmax, tmin, rainy, counted, cloud, total, wind, gust = ([] for _ in range(8))
        for k, day in enumerate(days, 1):
            band = min(k, mos.LAST_BAND)
            hours = local_hours(day)
            temps = self.whole_day(hours, "temperature_2m")
            highs = [self.correct(runs[m], "tmax", band, None, max(v)) for m, v in temps.items()]
            lows = [self.correct(runs[m], "tmin", band, None, min(v)) for m, v in temps.items()]
            tmax.append(([h for h in highs if h is not None], band))
            tmin.append(([low for low in lows if low is not None], band))
            # Rounded, so that 0.3 + 0.3 + 0.4 still reaches 1 mm.
            sums = [round(sum(v), 3) for v in self.whole_day(hours, "precipitation").values()]
            rainy.append(sum(s >= RAIN_DAY_MM for s in sums))
            counted.append(len(sums))
            total.append(_mean(sums))
            covers = self.whole_day(hours, "cloud_cover").values()
            cloud.append(_mean([fmean(v) for v in covers], 0))
            winds = self.whole_day(hours, "wind_speed_10m").values()
            wind.append(_mean([max(v) * KMH_PER_MS for v in winds]))
            gusts = self.whole_day(hours, "wind_gusts_10m").values()
            gust.append(_mean([max(v) * KMH_PER_MS for v in gusts]))
        return Daily(
            day=days,
            tmax_c=_spread(tmax),
            tmin_c=_spread(tmin),
            rain=RainCount(threshold_mm=RAIN_DAY_MM, n_models=rainy, m_models=counted),
            cloud_pct=Consensus(corrected=False, mean=cloud),
            precipitation_mm=Consensus(corrected=False, mean=total),
            wind_max_kmh=Consensus(corrected=False, mean=wind),
            gust_max_kmh=Consensus(corrected=False, mean=gust),
        )


def local_hours(day: date) -> list[datetime]:
    """The instants in (D 00:00, D+1 00:00] Europe/Rome, as T12 counts a local day."""
    start = datetime.combine(day, time(), ROME).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time(), ROME).astimezone(UTC)
    return [start + k * HOUR for k in range(1, (end - start) // HOUR + 1)]


def build(
    town: Town, runs: list[ModelRun], coefficients: mos.Coefficients | None, issued: datetime
) -> Forecast:
    issue = Issue(runs, coefficients, town.reference.id, issued)
    hourly, daily = issue.hourly(), issue.daily()
    return Forecast(
        license=LICENSE,
        attribution=ATTRIBUTION,
        generated_at=issued,
        town=town.slug,
        issued_at=issued,
        method=mos.METHOD,
        models=[Run(model=r.model, run_init=r.run_init) for r in runs if r.model in issue.used],
        hourly=hourly,
        daily=daily,
    )


def issued_name(slug: str, issued: datetime) -> str:
    return f"v1/{slug}/{issued:%Y/%m/%d}/{issued:%Y%m%dT%H%M%SZ}-forecast.json"


def publish(lake: Store, public: Store, towns: list[Town], now: datetime) -> None:
    """Keeps each town's issue in the forecasts container, then publishes it. The
    container is write-once, so every file the site has shown is kept as it was."""
    issued = now.replace(microsecond=0)
    runs = newest_runs(lake, issued)
    found = coefficients(lake, issued.date())
    if found is None:
        log.error("forecast: no mean60 coefficients since %s", issued.date())
    for town in towns:
        body = build(town, runs, found, issued).body()
        lake.put_new(ISSUED, issued_name(town.slug, issued), body, "application/json")
        public.put("public", Forecast.path(town.slug), body, "application/json", Forecast.CACHE)
        log.info("forecast: %s issued, %d bytes", town.slug, len(body))
