"""The public status.json: when each source was last reached and how recent its data is.

Each source keeps the newest time per station, point or model under `parts`, and
`data_time` is the oldest of them, so one dead station shows. For model runs it is
the newest instead: any fresh run means the forecasts are current.

Every job updates only its own entry. Jobs run at the same time (on Flex each
timer function scales on instances of its own), so the file is replaced only if
nobody wrote it since it was read.
"""

import json
from collections.abc import Collection
from datetime import UTC, datetime, timedelta

from meteo.store import Store

NAME = "status.json"
CONTAINER = "public"
NEWEST_WINS = {"open-meteo", "ensemble"}

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
    "arpa": (1080, 360),
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
        status = json.loads(body) if body else {"sources": {}}
        entry = status["sources"].setdefault(source, {})
        stored = entry.get("parts", {})
        parts = {k: parse_stamp(v) for k, v in stored.items() if k in expected}
        for part, t in newest.items():
            if part in expected:
                parts[part] = max(t, parts[part]) if part in parts else t
        if checked_at is not None:
            entry["checked_at"] = stamp(checked_at)
        if parts:
            pick = max if source in NEWEST_WINS else min
            entry["data_time"] = stamp(pick(parts.values()))
        else:
            entry.pop("data_time", None)
        entry["parts"] = {k: stamp(v) for k, v in sorted(parts.items())}
        status["generated_at"] = stamp(datetime.now(UTC))
        data = json.dumps(status, indent=1, sort_keys=True).encode()
        if public.swap(CONTAINER, NAME, data, etag, "application/json", "public, max-age=60"):
            return
    raise RuntimeError(f"{NAME} kept changing under the {source} job")


def late_sources(status: dict, now: datetime) -> list[str]:
    late = []
    for source, (data_minutes, checked_minutes) in LIMITS.items():
        entry = status["sources"].get(source, {})
        for key, minutes in (("data_time", data_minutes), ("checked_at", checked_minutes)):
            if key not in entry or now - parse_stamp(entry[key]) > timedelta(minutes=minutes):
                late.append(f"{source} {key}")
    return late
