"""The body of each timer, given the lake and the public store. function_app.py runs
them on Azure; `python -m meteo` runs them against a local folder."""

import contextlib
import ctypes
import gc
import json
import logging
import tempfile
import time
from collections.abc import Callable, Collection, Iterator, Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import requests

from meteo import (
    arpa,
    compact,
    forecast,
    metar,
    mos,
    mosmix,
    now,
    openmeteo,
    radar,
    sprites,
    status,
    towns,
    web,
    yr,
)
from meteo.store import Store
from meteo.towns import Town

log = logging.getLogger(__name__)

# Yr is asked on four hourly runs a day, 16 requests for the four points.
YR_HOURS = {4, 10, 16, 22}
# Off those hours Yr is asked again only when its last complete fetch is older
# than this. The slots are 6 h apart and the runs hourly, so a day with no
# failure never gets there; a failed slot is tried again on the next run.
YR_RETRY_AFTER = timedelta(minutes=330)
# At most this long for the nightly radar repair, so compaction keeps its time.
REPAIR_MINUTES = 5


class SourceFailed(Exception):
    pass


def peak_mb() -> int | None:
    """The worker process's peak resident memory so far, in MB. It includes earlier
    runs on the same instance; Windows, where dry runs happen, has no `resource`."""
    try:
        import resource
    except ImportError:
        return None
    # ru_maxrss is in KiB on Linux.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024


def _release() -> None:
    """Hands what the last step freed back to the system. glibc keeps freed blocks
    for later, so without it the resident set stays near the last step's peak and
    the next step starts from there."""
    gc.collect()
    with contextlib.suppress(OSError):
        ctypes.CDLL("libc.so.6").malloc_trim(0)


def _reset_peak() -> bool:
    """Writing 5 to clear_refs sets the resident set's high-water mark (VmHWM) back
    to the current size. False where there is no such file, as on Windows."""
    try:
        Path("/proc/self/clear_refs").write_text("5")
    except OSError:
        return False
    return True


def high_water_mb(status: str) -> int | None:
    """VmHWM from the text of /proc/self/status, which gives it in kB."""
    for line in status.splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1]) // 1024
    return None


@contextlib.contextmanager
def step(name: str) -> Iterator[None]:
    """Logs the step's own peak resident memory, unlike peak_mb, which keeps the
    highest of the worker's whole life, earlier invocations on the instance included."""
    _release()
    reset = _reset_peak()
    try:
        yield
    finally:
        peak = high_water_mb(Path("/proc/self/status").read_text()) if reset else None
        log.info("%s: step peak %s MB", name, peak)
        _release()


def _collect(
    public: Store,
    source: str,
    collect: Callable[[dict[str, datetime]], None],
    expected: Collection[str],
) -> bool:
    """Runs one source and records it in status.json. `collect` fills the dict it is
    given with the newest time it holds per part (station, sensor, point or model);
    `expected` lists the parts that count. What a source archived before it failed
    is recorded too, but the check does not count as done."""
    newest: dict[str, datetime] = {}
    checked = datetime.now(UTC)
    try:
        collect(newest)
        ok = True
    except Exception:
        log.exception("%s failed", source)
        ok = False
    status.record(public, source, checked if ok else None, newest, expected)
    return ok


def yr_due(now: datetime, current: dict) -> bool:
    if now.hour in YR_HOURS:
        return True
    checked = current["sources"].get("yr", {}).get("checked_at")
    return checked is None or now - status.parse_stamp(checked) > YR_RETRY_AFTER


def _radar_session(env: Mapping[str, str]) -> requests.Session:
    # DPC answers 500 for a frame it never made, so a 500 is not worth retrying here.
    return web.session(env["USER_AGENT"], retry_on=(429, 502, 503, 504))


def _newest_frame(public: Store) -> datetime | None:
    archived = status.read(public)["sources"].get("radar", {}).get("data_time")
    return status.parse_stamp(archived) if archived else None


def radar_frames(
    lake: Store, public: Store, env: Mapping[str, str], town_dir: Path, minutes: float
) -> None:
    """New frames into the lake, then each town's sprite, radar.json and the radar
    block of now.json, also after a failed fetch: what did arrive is published."""
    deadline = time.monotonic() + minutes * 60
    since = _newest_frame(public)
    http = _radar_session(env)
    origin = env["RADAR_ORIGIN"]

    def collect(newest):
        radar.collect(lake, http, origin, since, deadline, newest)

    ok = _collect(public, "radar", collect, {"sri"})
    latest = _newest_frame(public)
    if latest is not None:
        all_towns = towns.load(town_dir)
        sprites.publish(lake, public, all_towns, latest)
        now.publish_radar(lake, public, all_towns, latest)
    if not ok:
        raise SourceFailed("radar")


def radar_repair(lake: Store, env: Mapping[str, str], day: date, minutes: float) -> None:
    """Fills the day's missing frames and records the ones DPC itself lacks, which
    compaction copies into the day's completeness file."""
    deadline = time.monotonic() + minutes * 60
    gaps = radar.repair(lake, _radar_session(env), env["RADAR_ORIGIN"], day, deadline)
    if gaps is None:
        raise SourceFailed(f"radar repair of {day} ran out of time")
    body = {
        "day": day.isoformat(),
        "checked_at": status.stamp(datetime.now(UTC)),
        "source_gaps": [f"{g:%H:%M}" for g in gaps],
    }
    data = json.dumps(body, indent=1).encode()
    lake.put("curated", compact.radar_gaps_name(day), data, "application/json")


def metar_reports(lake: Store, public: Store, env: Mapping[str, str], town_dir: Path) -> None:
    """New reports into the lake, then the METAR block of each town's now.json."""
    all_towns = towns.load(town_dir)
    icaos = [a.icao for a in towns.airports(all_towns) if a.icao]
    http = web.session(env["USER_AGENT"])
    ok = _collect(public, "metar", lambda n: metar.collect(lake, http, icaos, n), icaos)
    now.publish_metar(lake, public, all_towns, datetime.now(UTC))
    if not ok:
        raise SourceFailed("metar")


def _arpa(
    lake: Store, public: Store, env: Mapping[str, str], all_towns: list[Town], variant: str
) -> bool:
    sensors = [s.id for s in towns.arpa_sensors(all_towns)]
    # dati.lombardia.it turns most requests away in bursts and sends no Retry-After:
    # on 21-22/10 four live pulls in seven failed after three tries in a minute.
    # Six tries take about seven minutes, which the live job has; the nightly
    # keeps three, since its 30-day pull can miss a night and compaction cannot.
    http = web.session(env["USER_AGENT"], retries=6 if variant == "live" else 3)
    token = env.get("ARPA_APP_TOKEN")
    # An app setting whose Key Vault reference did not resolve keeps the reference text.
    if token and token.startswith("@Microsoft.KeyVault("):
        raise SourceFailed("ARPA_APP_TOKEN is a Key Vault reference that did not resolve")
    # Freshness follows the reference stations' own sensors only.
    reference = {str(s) for s in towns.reference_sensors(all_towns)}
    return _collect(
        public, "arpa", lambda n: arpa.collect(lake, http, token, sensors, variant, n), reference
    )


def arpa_stations(lake: Store, public: Store, env: Mapping[str, str], town_dir: Path) -> None:
    if not _arpa(lake, public, env, towns.load(town_dir), "live"):
        raise SourceFailed("arpa")


def hourly_forecasts(
    lake: Store, public: Store, env: Mapping[str, str], town_dir: Path, minutes: float
) -> None:
    """Model runs, best_match, MOSMIX and Yr, then each town's forecast from the
    newest runs, then the check that every source is recent. One source failing does
    not stop the others; the run fails at the end, and the failed run is what the
    alert watches."""
    deadline = time.monotonic() + minutes * 60
    all_towns = towns.load(town_dir)
    points = towns.forecast_points(all_towns)
    wmos = [a.wmo for a in towns.airports(all_towns) if a.wmo]
    http = web.session(env["USER_AGENT"])
    sources: dict[str, tuple[Callable[[dict[str, datetime]], None], Collection[str]]] = {
        "open-meteo": (
            lambda n: openmeteo.collect_runs(lake, http, points, "nwp", deadline, n),
            openmeteo.MODELS,
        ),
        "ensemble": (
            lambda n: openmeteo.collect_runs(lake, http, points, "ensemble", deadline, n),
            openmeteo.ENSEMBLES,
        ),
        "best_match": (lambda n: openmeteo.collect_best_match(lake, http, points), ()),
        "mosmix": (
            lambda n: mosmix.collect(lake, http, wmos, deadline, n),
            [str(w) for w in wmos],
        ),
    }
    if yr_due(datetime.now(UTC), status.read(public)):
        sources["yr"] = (
            lambda n: yr.collect(lake, http, points, deadline, n),
            [p.id for p in points],
        )
    failed = [
        source
        for source, (collect, expected) in sources.items()
        if not _collect(public, source, collect, expected)
    ]
    try:
        forecast.publish(lake, public, all_towns, datetime.now(UTC))
    except Exception:
        log.exception("forecast failed")
        failed.append("forecast")

    late = status.late_sources(status.read(public), datetime.now(UTC))
    if failed or late:
        raise SourceFailed(
            f"failed: {', '.join(failed) or 'none'}; late: {', '.join(late) or 'none'}"
        )


def compact_day(
    lake: Store, all_towns: list[Town], day: date, deadline: float, today: date
) -> None:
    points = {p.id: (p.lat, p.lon) for p in towns.forecast_points(all_towns)}
    points |= {t.slug: (t.lat, t.lon) for t in all_towns}
    centres = [(t.lat, t.lon) for t in all_towns]
    compact.run(lake, day, towns.arpa_sensors(all_towns), points, centres, deadline, today)


def nightly(
    lake: Store, public: Store, env: Mapping[str, str], town_dir: Path, minutes: float, today: date
) -> None:
    """Yesterday's radar repair, the 30-day ARPA pull, then compaction of the days
    that are due. A failed step does not stop the next one; the run fails at the end."""
    deadline = time.monotonic() + minutes * 60
    all_towns = towns.load(town_dir)
    failed = []
    try:
        with step("radar repair"):
            radar_repair(lake, env, today - timedelta(days=1), REPAIR_MINUTES)
    except Exception:
        log.exception("radar repair failed")
        failed.append("radar repair")
    with step("30-day ARPA pull"):
        if not _arpa(lake, public, env, all_towns, "revision"):
            failed.append("30-day ARPA pull")
    for day in compact.days_due(lake, today):
        with step(f"compaction of {day}"):
            compact_day(lake, all_towns, day, deadline, today)
    if failed:
        raise SourceFailed(f"{', '.join(failed)} failed")


def mean60(lake: Store, town_dir: Path, today: date) -> None:
    """Today's mean60 coefficients, on a timer of their own after the nightly, so that
    the compaction's memory is not still held while they are fitted."""
    with step("mean60 coefficients"):
        mean60_coefficients(lake, towns.load(town_dir), today)


def _curated(lake: Store, tmp: Path, table: str, first: date, last: date) -> list[Path]:
    """Copies the table's files from first to last into tmp; days without one are skipped."""
    paths = []
    for n in range((last - first).days + 1):
        name = compact.curated_name(table, first + timedelta(days=n))
        if lake.exists("curated", name):
            path = tmp / name
            path.parent.mkdir(parents=True, exist_ok=True)
            lake.download("curated", name, path)
            paths.append(path)
    return paths


def mean60_coefficients(lake: Store, all_towns: list[Town], day: date) -> None:
    """Rewrites the coefficients of `day` (mos.py) from the curated tables: model runs
    of the 70 days before its window ends, the backfilled runs, and ARPA's hours and
    days at the forecast points that have a station."""
    stations = {
        s.id: s.arpa_station
        for t in all_towns
        for s in (t.reference, t.inland)
        if s is not None and s.arpa_station is not None
    }
    first, last = mos.window(day)
    with tempfile.TemporaryDirectory() as folder:
        tmp = Path(folder)
        # A run started up to 10 days before the window still has valid times in it.
        runs = _curated(lake, tmp, "nwp_hourly", first - timedelta(days=10), last)
        backfill = _curated(lake, tmp, "nwp_prev", first, last)
        hours = _curated(lake, tmp, "obs_arpa_hourly", first, last)
        days = _curated(lake, tmp, "obs_arpa_daily", first, last)
        if not (hours and days):
            raise SourceFailed(f"no ARPA tables from {first} to {last}")
        # On 70 run days of 94 fetches in Linux: 341 MB at 256 MB and two threads,
        # 237 MB with these, in under 4 s instead of 2.
        with compact.connect(tmp, "96MB", threads=1, lean=True) as con:
            mos.load(con, stations, hours, days, nwp_hourly=runs, nwp_prev=backfill)
            body = mos.coefficients(con, day)
    lake.put("curated", mos.name(day), body, "application/json")
    log.info(
        "mean60: %s from %d run days, %d backfilled, %d ARPA days",
        day,
        len(runs),
        len(backfill),
        len(days),
    )
