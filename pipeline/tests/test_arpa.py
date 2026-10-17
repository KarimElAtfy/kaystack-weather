import gzip
import json
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

from conftest import fixture, replaying

from meteo import arpa


def query(request) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(request.url).query).items()}


def test_a_pull_is_stored_gzipped_with_the_newest_end_per_sensor(lake):
    body = fixture("arpa/live-sample.json")
    http, replay = replaying({("GET", arpa.URL): (200, body, {})})
    newest = {}
    arpa.collect(lake, http, "token-for-tests", [8145, 32353], "live", newest)

    (name,) = lake.names("raw", "arpa/")
    assert name.endswith("-live.json.gz")
    assert gzip.decompress(lake.read("raw", name)[0]) == body
    # The newest label in the sample is 11:00 in UTC+1, so 10:00 UTC.
    assert newest["8145"] == datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
    sent = replay.sent[0]
    assert sent.headers["X-App-Token"] == "token-for-tests"
    asked = query(sent)
    assert asked["$where"].startswith("idsensore in('8145','32353') AND data > '")
    assert asked["$select"] == "idsensore,data,valore,idoperatore,stato"


def test_a_full_page_asks_for_the_next_one(lake, monkeypatch):
    monkeypatch.setattr(arpa, "PAGE", 3)
    rows = json.loads(fixture("arpa/live-sample.json"))

    def page(request):
        offset = int(query(request)["$offset"])
        return 200, json.dumps(rows[offset : offset + 3]).encode(), {}

    http, replay = replaying({("GET", arpa.URL): page})
    arpa.collect(lake, http, None, [8145], "revision", {})
    # 42 rows in pages of 3, then the empty page that ends it.
    assert len(rows) == 42
    assert len(replay.sent) == 15
    variants = {name.split("-", 1)[1] for name in lake.names("raw", "arpa/")}
    assert len(variants) == 14
    assert {"revision.json.gz", "revision-p1.json.gz", "revision-p13.json.gz"} <= variants
    assert "X-App-Token" not in replay.sent[0].headers


def test_no_rows_stores_nothing(lake):
    http, _ = replaying({("GET", arpa.URL): (200, b"[]", {})})
    newest = {}
    arpa.collect(lake, http, None, [8145], "live", newest)
    assert lake.names("raw", "arpa/") == []
    assert newest == {}
