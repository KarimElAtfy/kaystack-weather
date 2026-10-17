"""The "7 complete days" check that closes M1, run once by hand.

A day passes when the lake holds everything the source held. The lake side comes
from the completeness file compaction wrote for the day. The source side is asked
again now: DPC for every radar slot the lake lacks, ARPA for its own count per
sensor and operator, the IEM archive for the METARs. Gaps the source also has are
allowed; the run is meant for days at least two days old, when ARPA is complete.
"""

import csv
import io
import json
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta

import requests

from meteo import arpa, compact, radar, web
from meteo.store import Store, day_prefix, raw_name
from meteo.towns import Town, airports, arpa_sensors, forecast_points

IEM = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

# Runs started on one day, per model.
RUNS = {
    "ecmwf_ifs": 4,
    "ecmwf_aifs025_single": 4,
    "icon_d2": 8,
    "icon_eu": 8,
    "italia_meteo_arpae_icon_2i": 2,
    "meteoswiss_icon_ch1": 8,
    "meteoswiss_icon_ch2": 4,
    "meteofrance_arome_france_hd": 8,
    "ukmo_global_deterministic_10km": 4,
    "gfs_global": 4,
    "best_match": 24,
}
ENSEMBLE_RUNS = {
    "ecmwf_ifs025_ensemble": 4,
    "icon_eu_eps": 4,
    "icon_d2_eps": 8,
    "meteoswiss_icon_ch1_ensemble": 8,
    "meteoswiss_icon_ch2_ensemble": 4,
}

type Row = tuple[str, bool, str]


def _short(have: Mapping[str, int], want: Mapping[str, int]) -> list[str]:
    return [f"{k} {have.get(k, 0)}/{n}" for k, n in want.items() if have.get(k, 0) < n]


def _radar(lake: Store, http: requests.Session, origin: str, day: date) -> Row:
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    stored = set(lake.names("raw", day_prefix("radar", day)))
    missing = [
        start + slot * radar.STEP
        for slot in range(288)
        if raw_name("radar", start + slot * radar.STEP, "sri", "u16.zlib") not in stored
    ]
    at_source = [f"{m:%H:%M}" for m in missing if radar.link(http, origin, m) is not None]
    detail = f"{288 - len(missing)} of 288 stored, {len(missing) - len(at_source)} absent at DPC"
    if at_source:
        detail += f"; DPC has {', '.join(at_source)}"
    return ("radar", not at_source, detail)


def _arpa(http: requests.Session, token: str | None, sensors: list[int], day: date, counts) -> Row:
    # Labels are UTC+1 interval ends: UTC day D is (D 01:00, D+1 01:00] in labels.
    first = f"{day:%Y-%m-%d}T01:00:00"
    last = f"{day + timedelta(days=1):%Y-%m-%d}T01:00:00"
    ids = ",".join(f"'{s}'" for s in sensors)
    response = http.get(
        arpa.URL,
        params={
            "$select": "idsensore,idoperatore,count(*)",
            "$where": f"idsensore in({ids}) AND data > '{first}' AND data <= '{last}'",
            "$group": "idsensore,idoperatore",
        },
        headers={"X-App-Token": token} if token else {},
        timeout=(5, 120),
    )
    response.raise_for_status()
    theirs = {f"{r['idsensore']}/{r['idoperatore']}": int(r["count"]) for r in response.json()}
    ours = counts.get("arpa", {})
    differ = [f"{k} {ours.get(k, 0)}/{n}" for k, n in sorted(theirs.items()) if ours.get(k, 0) != n]
    detail = f"{sum(ours.values())} values, ARPA has {sum(theirs.values())}"
    if differ:
        detail += f"; lake/ARPA differ: {', '.join(differ)}"
    return ("arpa", not differ, detail)


def _metar(http: requests.Session, icaos: list[str], day: date, counts) -> Row:
    after = day + timedelta(days=1)
    response = http.get(
        IEM,
        params=[
            *[("station", i) for i in icaos],
            ("data", "metar"),
            ("year1", day.year),
            ("month1", day.month),
            ("day1", day.day),
            ("year2", after.year),
            ("month2", after.month),
            ("day2", after.day),
            ("tz", "Etc/UTC"),
            ("format", "onlycomma"),
            # Routine reports and specials.
            ("report_type", 3),
            ("report_type", 4),
        ],
        timeout=(5, 120),
    )
    response.raise_for_status()
    theirs = {(r["station"], r["valid"][11:16]) for r in csv.DictReader(io.StringIO(response.text))}
    ours = {
        (icao, t) for icao, entry in counts.get("metar", {}).items() for t in entry["obs_times"]
    }
    lacking = sorted(theirs - ours)
    routine = {icao: entry["routine"] for icao, entry in sorted(counts.get("metar", {}).items())}
    detail = f"routine {routine}, IEM has {len(theirs)} reports"
    if lacking:
        detail += f"; lake lacks {', '.join(f'{i} {t}' for i, t in lacking)}"
    return ("metar", not lacking, detail)


def check_day(lake: Store, env: Mapping[str, str], all_towns: list[Town], day: date) -> list[Row]:
    name = compact.completeness_name(day)
    if not lake.exists("curated", name):
        return [("compaction", False, f"no {name}")]
    counts = json.loads(lake.read("curated", name)[0])
    http = web.session(env["USER_AGENT"])
    radar_http = web.session(env["USER_AGENT"], retry_on=(429, 502, 503, 504))
    sensors = [s.id for s in arpa_sensors(all_towns)]
    icaos = [a.icao for a in airports(all_towns) if a.icao]
    wmos = {str(a.wmo): 4 for a in airports(all_towns) if a.wmo}
    points = {p.id: 4 for p in forecast_points(all_towns)}
    rows = [
        _radar(lake, radar_http, env["RADAR_ORIGIN"], day),
        _arpa(http, env.get("ARPA_APP_TOKEN"), sensors, day, counts),
        _metar(http, icaos, day, counts),
    ]
    for source, have, want in (
        ("open-meteo", counts.get("nwp", {}), RUNS),
        ("ensemble", counts.get("ensemble", {}), ENSEMBLE_RUNS),
        ("mosmix", counts.get("mosmix", {}), wmos),
        ("yr", counts.get("yr", {}), points),
    ):
        short = _short(have, want)
        rows.append(
            (source, not short, "; ".join(short) or f"{sum(want.values())} expected, all in")
        )
    return rows


def run(
    lake: Store, env: Mapping[str, str], all_towns: list[Town], first: date, last: date
) -> bool:
    passed = True
    day = first
    while day <= last:
        for source, ok, detail in check_day(lake, env, all_towns, day):
            print(f"{day}  {source:<10}  {'pass' if ok else 'FAIL'}  {detail}")
            passed = passed and ok
        day += timedelta(days=1)
    return passed
