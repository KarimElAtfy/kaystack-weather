"""The public status.json: when each source was last reached and how recent its data is.

Each source keeps the newest time per station, point or model under `parts`, and
`data_time` is the oldest of them, so one dead station shows. For model runs it is
the newest instead: any fresh run means the forecasts are current.

Every job updates only its own entry. Jobs run at the same time (on Flex each
timer function scales on instances of its own), so the file is replaced only if
nobody wrote it since it was read. It is written through the contract's Status, so
a time not known yet is null rather than left out.
"""

import json
from collections.abc import Collection
from datetime import UTC, datetime, timedelta

from meteo.contract import Status
from meteo.store import Store

NAME = Status.PATH
CONTAINER = "public"
NEWEST_WINS = {"open-meteo", "ensemble"}
# Files written before the contract left out the times not known yet.
UNKNOWN = {"checked_at": None, "data_time": None}
LICENSE = "CC BY-SA 4.0"
ATTRIBUTION = (
    "Radar-DPC, Open-Meteo.com, NOAA Aviation Weather Center, ARPA Lombardia, DWD, MET Norway"
)

# Minutes since data_time and since checked_at. These make the hourly run fail,
# which sends the alert. freshness.yml keeps a copy, so that the check from
# outside does not depend on this code; a test keeps the two equal.
LIMITS = {
    "radar": (30, 15),
    "metar": (90, 60),
    "open-meteo": (360, 120),
    # D2-EPS and CH1-EPS runs land at R+2:45, so at :17 the newest start can be
    # 5 h 17 min old: 360 would leave 43 minutes for a late run.
    "ensemble": (420, 120),
    # ARPA stopped publishing on Sunday 2026-10-18: values ending about 04:20 UTC
    # stayed the newest until after midnight, 21 h. It serves training and
    # verification only, so 2880 matches the live pull's 48 h lookback: a longer
    # stall leaves a gap that only the nightly 30-day pull fills.
    "arpa": (2880, 360),
    # An issue listed at :12-:16 is stored at :45, so the age reaches 7 h 17 min
    # at :17; with 480, one DWD delay past :45 would mail.
    "mosmix": (540, 120),
    # Yr is asked every 6 h and gets what MET last updated, which can be hours
    # older: the 16:45 fetch on 2026-10-17 got 13:17, 9 h old by 22:17. 720
    # allows for up to 6 h between two MET updates.
    "yr": (720, 420),
}


def stamp(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_stamp(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def read(public: Store) -> dict:
    body, _ = public.read_versioned(CONTAINER, NAME)
    return json.loads(body) if body else {"sources": {}}


def record(
    public: Store,
    source: str,
    checked_at: datetime | None,
    newest: dict[str, datetime],
    expected: Collection[str],
) -> None:
    """checked_at None keeps the previous one: the source was not reached in full.
    Parts not in `expected` are dropped, so a sensor ARPA replaced or a point taken
    out of the town files stops holding data_time back."""
    for _ in range(5):
        body, etag = public.read_versioned(CONTAINER, NAME)
        sources = json.loads(body)["sources"] if body else {}
        entry = sources.setdefault(source, {})
        stored = entry.get("parts", {})
        parts = {k: parse_stamp(v) for k, v in stored.items() if k in expected}
        for part, t in newest.items():
            if part in expected:
                parts[part] = max(t, parts[part]) if part in parts else t
        if checked_at is not None:
            entry["checked_at"] = stamp(checked_at)
        pick = max if source in NEWEST_WINS else min
        entry["data_time"] = stamp(pick(parts.values())) if parts else None
        entry["parts"] = {k: stamp(v) for k, v in sorted(parts.items())}
        status = Status(
            license=LICENSE,
            attribution=ATTRIBUTION,
            generated_at=datetime.now(UTC),
            sources={k: UNKNOWN | v for k, v in sorted(sources.items())},
        )
        if public.swap(CONTAINER, NAME, status.body(), etag, "application/json", Status.CACHE):
            return
    raise RuntimeError(f"{NAME} kept changing under the {source} job")


def late_sources(status: dict, now: datetime) -> list[str]:
    late = []
    for source, (data_minutes, checked_minutes) in LIMITS.items():
        entry = status["sources"].get(source, {})
        for key, minutes in (("data_time", data_minutes), ("checked_at", checked_minutes)):
            if entry.get(key) is None or now - parse_stamp(entry[key]) > timedelta(minutes=minutes):
                late.append(f"{source} {key}")
    return late
