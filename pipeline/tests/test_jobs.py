from datetime import UTC, datetime

import pytest
from conftest import TOWNS

from meteo import jobs, status

T = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


def test_an_unresolved_key_vault_reference_stops_the_arpa_job(lake):
    env = {
        "USER_AGENT": "weather.kaystack.dev github.com/KarimElAtfy/kaystack-weather",
        "ARPA_APP_TOKEN": "@Microsoft.KeyVault(SecretUri=https://kv-kaystack-meteo.vault.azure.net/secrets/arpa-app-token/)",
    }
    with pytest.raises(jobs.SourceFailed, match="Key Vault"):
        jobs.arpa_stations(lake, lake, env, TOWNS)
    assert lake.names("raw", "") == []


def test_a_source_that_fails_halfway_keeps_what_it_archived(lake):
    status.record(lake, "radar", T, {"sri": T}, {"sri"})

    def collect(newest):
        newest["sri"] = datetime(2026, 10, 16, 12, 5, tzinfo=UTC)
        raise ConnectionError("recorded for the test")

    assert not jobs._collect(lake, "radar", collect, {"sri"})
    radar = status.read(lake)["sources"]["radar"]
    assert radar["data_time"] == "2026-10-16T12:05:00Z"
    assert radar["checked_at"] == "2026-10-16T12:00:00Z"


@pytest.mark.parametrize(
    ("now", "last_complete_fetch", "due"),
    [
        ("2026-10-16T10:45:00Z", "2026-10-16T04:45:01Z", True),
        # The normal day: off the four hours, at most 5 h after a good slot.
        ("2026-10-16T05:45:00Z", "2026-10-16T04:45:01Z", False),
        ("2026-10-16T09:45:00Z", "2026-10-16T04:45:01Z", False),
        # The 04:45 slot failed, so the last complete fetch is the 22:45 one.
        ("2026-10-16T05:45:00Z", "2026-10-15T22:45:01Z", True),
        ("2026-10-16T06:45:00Z", "2026-10-16T05:45:02Z", False),
        ("2026-10-16T05:45:00Z", None, True),
    ],
)
def test_yr_is_asked_on_its_hours_and_again_after_a_failed_slot(now, last_complete_fetch, due):
    yr = {"checked_at": last_complete_fetch} if last_complete_fetch else {}
    current = {"sources": {"yr": yr}}
    assert jobs.yr_due(status.parse_stamp(now), current) is due
