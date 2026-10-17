import functools
import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import azure.functions as func

from meteo import jobs
from meteo.store import AzureStore

# The storage SDK logs every request at INFO, which would fill Application Insights.
logging.getLogger("azure").setLevel(logging.WARNING)

HERE = Path(__file__).parent
# The deploy package carries a copy of towns/ next to this file; a checkout has it one level up.
TOWNS = HERE / "towns" if (HERE / "towns").is_dir() else HERE.parent / "towns"


log = logging.getLogger("meteo")


def run(job: Callable[..., None], *args, **kwargs) -> None:
    # One line per run, failed or not, so that the week-1 measurement can read the
    # peak memory per job next to its GB-s.
    try:
        job(*args, **kwargs)
    finally:
        log.info("%s: peak memory %s MB", job.__name__, jobs.peak_mb())


@functools.cache
def store(setting: str) -> AzureStore:
    from azure.identity import ManagedIdentityCredential

    return AzureStore(os.environ[setting], ManagedIdentityCredential())


timers = func.Blueprint()

# Schedules are UTC: Flex Consumption has no WEBSITE_TIME_ZONE. A timer does not
# start again while its previous run is still going, so a slow run skips a slot.


# DPC lists frame T about 8 minutes after T. A missed run is caught up by the
# next, so the schedule is not monitored and costs no status writes.
@timers.timer_trigger(
    schedule="0 4,9,14,19,24,29,34,39,44,49,54,59 * * * *", arg_name="timer", use_monitor=False
)
def radar(timer: func.TimerRequest) -> None:
    run(jobs.radar_frames, store("LAKE_ACCOUNT"), store("PUBLIC_ACCOUNT"), os.environ, minutes=4)


# Reports are made at :20 and :50 and reach AWC 5 to 14 minutes later.
@timers.timer_trigger(schedule="0 7,37 * * * *", arg_name="timer", use_monitor=False)
def metar(timer: func.TimerRequest) -> None:
    run(jobs.metar_reports, store("LAKE_ACCOUNT"), store("PUBLIC_ACCOUNT"), os.environ, TOWNS)


# ICON-D2 is available about 86 minutes after its start, plus the 10 minutes
# Open-Meteo asks for: :45 takes it in the same hour.
@timers.timer_trigger(schedule="0 45 * * * *", arg_name="timer")
def hourly(timer: func.TimerRequest) -> None:
    lake, public = store("LAKE_ACCOUNT"), store("PUBLIC_ACCOUNT")
    run(jobs.hourly_forecasts, lake, public, os.environ, TOWNS, minutes=12)


@timers.timer_trigger(schedule="0 40 2,5,8,11,14,17,20,23 * * *", arg_name="timer")
def arpa(timer: func.TimerRequest) -> None:
    run(jobs.arpa_stations, store("LAKE_ACCOUNT"), store("PUBLIC_ACCOUNT"), os.environ, TOWNS)


@timers.timer_trigger(schedule="0 30 1 * * *", arg_name="timer")
def nightly(timer: func.TimerRequest) -> None:
    lake, public = store("LAKE_ACCOUNT"), store("PUBLIC_ACCOUNT")
    today = datetime.now(UTC).date()
    run(jobs.nightly, lake, public, os.environ, TOWNS, minutes=13, today=today)


app = func.FunctionApp()
# In dev the app exists only for the spend-breaker drill. With no timer
# registered the host sits idle and no job ever runs there.
if os.environ.get("TIMERS_ENABLED") == "true":
    app.register_functions(timers)
