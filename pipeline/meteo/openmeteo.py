"""Open-Meteo forecasts at the forecast points: about ten deterministic models, the
ensembles, and best_match as a comparison.

A model run is fetched once, from 10 minutes after it became available, as Open-Meteo
asks. The raw name carries the run's start time, so a run already archived is
recognised by its name.

The forecast endpoint serves whatever a model holds at the moment of the request,
which meta.json read a moment before does not prove: gfs_global joins the 0.13 and
0.25 degree domains, and the 0.13 one gets each run about 90 minutes earlier. The
deterministic runs are therefore asked from Single Runs by their start time, every
one from the last archived to the newest, so a run that meta.json showed only
between two hourly checks, or never, is still fetched. Open-Meteo keeps no runs of
the ensembles, so for them the newest run is fetched and kept only if meta.json
shows the same run before and after the request.
"""

import gzip
import json
import logging
import time
from collections.abc import Collection, Iterator
from datetime import UTC, date, datetime, timedelta

import requests

from meteo.store import Store, day_prefix, name_time, raw_name
from meteo.towns import Station

log = logging.getLogger(__name__)

HOST = "https://api.open-meteo.com"
ENSEMBLE_HOST = "https://ensemble-api.open-meteo.com"
FORECAST = f"{HOST}/v1/forecast"
SINGLE_RUNS = "https://single-runs-api.open-meteo.com/v1/forecast"
ENSEMBLE = f"{ENSEMBLE_HOST}/v1/ensemble"
VARIABLES = [
    "temperature_2m",
    "dew_point_2m",
    "precipitation",
    "snowfall",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "pressure_msl",
    "shortwave_radiation",
]

# API model id: the domain whose meta.json announces its runs.
MODELS = {
    "ecmwf_ifs": "ecmwf_ifs",
    "ecmwf_aifs025_single": "ecmwf_aifs025_single",
    "icon_d2": "dwd_icon_d2",
    "icon_eu": "dwd_icon_eu",
    "italia_meteo_arpae_icon_2i": "italia_meteo_arpae_icon_2i",
    "meteoswiss_icon_ch1": "meteoswiss_icon_ch1",
    "meteoswiss_icon_ch2": "meteoswiss_icon_ch2",
    "meteofrance_arome_france_hd": "meteofrance_arome_france_hd",
    "ukmo_global_deterministic_10km": "ukmo_global_deterministic_10km",
    # gfs_global serves the 0.13 and 0.25 degree runs together, and the 0.25 one
    # lands about 90 minutes later. Waiting for it means both are there.
    "gfs_global": "ncep_gfs025",
}
ENSEMBLES = {
    "ecmwf_ifs025_ensemble": "ecmwf_ifs025_ensemble",
    "icon_eu_eps": "dwd_icon_eu_eps_native",
    "icon_d2_eps": "dwd_icon_d2_eps_native",
    "meteoswiss_icon_ch1_ensemble": "meteoswiss_icon_ch1_ensemble",
    "meteoswiss_icon_ch2_ensemble": "meteoswiss_icon_ch2_ensemble",
}
ENSEMBLE_VARIABLES = ["temperature_2m", "precipitation"]
# Kind: meta.json host, models, prefix of the raw variant.
KINDS = {
    "nwp": (HOST, MODELS, ""),
    "ensemble": (ENSEMBLE_HOST, ENSEMBLES, "ens-"),
}
SETTLE = timedelta(minutes=10)
# From the start of the run: day 10 of an issue ends up to 264 h after it, and a
# model's newest run can be a day older than the issue.
RUN_HOURS = 288
# At most this many runs of one model are caught up in one check, so that after an
# outage the calls are spread over the next checks.
CATCH_UP = 8

# meta.json answers 304 to its own ETag; the last answer is kept per domain while
# the instance lives.
_meta: dict[str, tuple[str, dict]] = {}


def meta(http: requests.Session, host: str, domain: str) -> dict:
    etag, cached = _meta.get(domain, ("", {}))
    response = http.get(
        f"{host}/data/{domain}/static/meta.json",
        headers={"If-None-Match": etag} if etag else {},
        timeout=(5, 20),
    )
    response.raise_for_status()
    if response.status_code == 304:
        return cached
    body = response.json()
    _meta[domain] = (response.headers.get("ETag", ""), body)
    return body


def _params(points: list[Station], variables: list[str], model: str) -> dict[str, str]:
    return {
        "latitude": ",".join(f"{p.lat:.4f}" for p in points),
        "longitude": ",".join(f"{p.lon:.4f}" for p in points),
        # The elevation makes Open-Meteo correct temperature to the station height.
        "elevation": ",".join(str(p.elevation_m) for p in points),
        "hourly": ",".join(variables),
        "models": model,
        # Runs that arrive late (UKMO 9 h, ECMWF 8 h) would otherwise lose their short leads.
        "past_hours": "12",
        # Counted from the request. Day 10 of an issue ends up to 264 h after it, and
        # the newest run of a model can have been fetched up to a day before.
        "forecast_hours": "288",
        "timezone": "GMT",
        "wind_speed_unit": "ms",
    }


def _fetch(
    lake: Store,
    http: requests.Session,
    url: str,
    params: dict[str, str],
    name: str,
    metadata: dict[str, str],
) -> None:
    response = http.get(url, params=params, timeout=(5, 60))
    response.raise_for_status()
    metadata = metadata | {
        "request": response.url,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    data = gzip.compress(response.content, mtime=0)
    lake.put_new("raw", name, data, "application/gzip", metadata)


def run_params(points: list[Station], model: str, run_init: datetime) -> dict[str, str]:
    params = _params(points, VARIABLES, model) | {
        "run": f"{run_init:%Y-%m-%dT%H:%M}",
        "forecast_hours": str(RUN_HOURS),
    }
    del params["past_hours"]
    return params


def fetch_run(
    lake: Store,
    http: requests.Session,
    points: list[Station],
    model: str,
    run_init: datetime,
    name: str,
    metadata: dict[str, str],
) -> bool:
    """Stores one deterministic run as Single Runs has it; False when Open-Meteo has
    no such run."""
    params = run_params(points, model, run_init)
    response = http.get(SINGLE_RUNS, params=params, timeout=(5, 60))
    if response.status_code == 400 and "not available" in response.text:
        return False
    response.raise_for_status()
    metadata = metadata | {
        "run_init": run_init.isoformat(),
        "points": ",".join(p.id for p in points),
        "request": response.url,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    data = gzip.compress(response.content, mtime=0)
    lake.put_new("raw", name, data, "application/gzip", metadata)
    return True


def missing_name(run_init: datetime, variant: str) -> str:
    """Where Open-Meteo's answer is kept for a run it never had."""
    return raw_name("open-meteo", run_init, variant, "missing.json")


def archived(lake: Store, days: list[date]) -> dict[str, dict[datetime, bool]]:
    """Per raw variant, the runs of the given days: True when archived, False when
    Open-Meteo answered that it never had them."""
    found: dict[str, dict[datetime, bool]] = {}
    for day in days:
        for name in lake.names("raw", day_prefix("open-meteo", day)):
            variant = name.rsplit("/", 1)[1].split("-", 1)[1].split(".", 1)[0]
            found.setdefault(variant, {})[name_time(name)] = name.endswith(".json.gz")
    return found


def due(held: Collection[datetime], newest: datetime, step: timedelta) -> list[datetime]:
    """The runs after the last one held, up to `newest`, at most CATCH_UP of them."""
    if not held:
        return [newest]
    runs: list[datetime] = []
    run = newest
    while run > max(held) and len(runs) < CATCH_UP:
        runs.append(run)
        run -= step
    return runs[::-1]


def collect_runs(
    lake: Store,
    http: requests.Session,
    points: list[Station],
    kind: str,
    deadline: float,
    newest: dict[str, datetime],
) -> None:
    host, models, prefix = KINDS[kind]
    now = datetime.now(UTC)
    # Three days: eight runs of a six-hourly model reach two days back.
    held = archived(lake, [(now - timedelta(days=d)).date() for d in (2, 1, 0)])
    failed = []
    for model, domain in models.items():
        if time.monotonic() > deadline:
            log.warning("open-meteo: deadline reached before %s", model)
            break
        variant = f"{prefix}{model}"
        runs = held.setdefault(variant, {})
        try:
            info = meta(http, host, domain)
            latest = datetime.fromtimestamp(info["last_run_initialisation_time"], UTC)
            available = datetime.fromtimestamp(info["last_run_availability_time"], UTC)
            settled = now >= available + SETTLE
            if kind == "nwp":
                step = timedelta(seconds=info["update_interval_seconds"])
                _catch_up(lake, http, points, model, runs, latest, available, settled, step)
            elif settled and latest not in runs:
                _fetch_newest(lake, http, points, model, domain, latest, available)
                runs[latest] = True
            stored = [run for run, kept in runs.items() if kept]
            if stored:
                newest[model] = max(stored)
        except requests.RequestException:
            log.exception("open-meteo: %s failed", model)
            failed.append(model)
    if failed:
        raise RuntimeError(f"open-meteo: {', '.join(failed)} failed")


def _catch_up(
    lake: Store,
    http: requests.Session,
    points: list[Station],
    model: str,
    runs: dict[datetime, bool],
    latest: datetime,
    available: datetime,
    settled: bool,
    step: timedelta,
) -> None:
    """Every run after the last archived one. The newest waits until it has settled;
    one before it that Open-Meteo does not have never came, and is marked missing."""
    for run_init in due(runs, latest if settled else latest - step, step):
        name = raw_name("open-meteo", run_init, model, "json.gz")
        # The availability meta.json gives is the newest run's alone.
        metadata = {"run_available": available.isoformat()} if run_init == latest else {}
        if fetch_run(lake, http, points, model, run_init, name, metadata):
            log.info("open-meteo: stored %s run %s", model, run_init)
            runs[run_init] = True
        elif run_init < latest:
            lake.put_new("raw", missing_name(run_init, model), b"{}", "application/json")
            log.warning("open-meteo: Open-Meteo has no %s run %s", model, run_init)
            runs[run_init] = False


def _fetch_newest(
    lake: Store,
    http: requests.Session,
    points: list[Station],
    model: str,
    domain: str,
    run_init: datetime,
    available: datetime,
) -> None:
    """The newest run of an ensemble, kept only if meta.json still shows it after the
    request: a run that landed during it would be filed under the one before."""
    params = _params(points, ENSEMBLE_VARIABLES, model)
    response = http.get(ENSEMBLE, params=params, timeout=(5, 60))
    response.raise_for_status()
    after = meta(http, ENSEMBLE_HOST, domain)["last_run_initialisation_time"]
    if datetime.fromtimestamp(after, UTC) != run_init:
        raise requests.RequestException(f"{model} moved on from run {run_init} during the fetch")
    metadata = {
        "run_init": run_init.isoformat(),
        "run_available": available.isoformat(),
        "points": ",".join(p.id for p in points),
        "request": response.url,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    name = raw_name("open-meteo", run_init, f"ens-{model}", "json.gz")
    lake.put_new(
        "raw", name, gzip.compress(response.content, mtime=0), "application/gzip", metadata
    )
    log.info("open-meteo: stored %s run %s", model, run_init)


def collect_best_match(lake: Store, http: requests.Session, points: list[Station]) -> None:
    fetched = datetime.now(UTC)
    name = raw_name("open-meteo", fetched, "best_match", "json.gz")
    metadata = {"points": ",".join(p.id for p in points)}
    _fetch(lake, http, FORECAST, _params(points, VARIABLES, "best_match"), name, metadata)


def _issue(metadata: dict[str, str]) -> tuple[datetime | None, datetime]:
    """The run start, or None for best_match, and the time leads count from."""
    if "run_init" in metadata:
        run_init = datetime.fromisoformat(metadata["run_init"])
        return run_init, run_init
    fetched = datetime.fromisoformat(metadata["fetched_at"])
    return None, fetched.replace(minute=0, second=0, microsecond=0)


def _hours(block: dict) -> list[datetime]:
    # With timezone=GMT the times are UTC and carry no offset.
    return [datetime.fromisoformat(t).replace(tzinfo=UTC) for t in block["time"]]


def hourly_rows(raw: bytes, metadata: dict[str, str], model: str) -> Iterator[dict]:
    """nwp_hourly rows. A response also carries older runs before the run start;
    only valid times from the run start on are kept."""
    run_init, origin = _issue(metadata)
    common = {
        "model": model,
        "run_init": run_init,
        "run_available": metadata.get("run_available"),
        "fetched_at": metadata["fetched_at"],
    }
    for point, answer in zip(metadata["points"].split(","), _answers(raw), strict=True):
        block = answer["hourly"]
        for i, valid in enumerate(_hours(block)):
            if valid >= origin:
                yield common | {
                    "point": point,
                    "valid": valid,
                    "lead_h": (valid - origin) // timedelta(hours=1),
                    **{v: block[v][i] for v in VARIABLES},
                }


def member_rows(raw: bytes, metadata: dict[str, str], model: str) -> Iterator[dict]:
    """One row per member and valid hour. The control is member 0."""
    run_init = datetime.fromisoformat(metadata["run_init"])
    for point, answer in zip(metadata["points"].split(","), _answers(raw), strict=True):
        block = answer["hourly"]
        numbered = (k for k in block if k.startswith("temperature_2m_member"))
        members = [0, *sorted(int(k.rsplit("member", 1)[1]) for k in numbered)]
        for i, valid in enumerate(_hours(block)):
            if valid < run_init:
                continue
            for m in members:
                suffix = f"_member{m:02d}" if m else ""
                yield {
                    "point": point,
                    "model": model,
                    "run_init": run_init,
                    "run_available": metadata.get("run_available"),
                    "fetched_at": metadata["fetched_at"],
                    "valid": valid,
                    "lead_h": (valid - run_init) // timedelta(hours=1),
                    "member": m,
                    "t2m": block[f"temperature_2m{suffix}"][i],
                    "pr": block[f"precipitation{suffix}"][i],
                }


def _answers(raw: bytes) -> list[dict]:
    body = json.loads(gzip.decompress(raw))
    # One point comes back as an object, several as a list in request order.
    return body if isinstance(body, list) else [body]
