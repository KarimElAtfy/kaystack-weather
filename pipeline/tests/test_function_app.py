import json
import os
import subprocess
import sys
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1]

# The host indexes functions by importing function_app; this does the same in a
# fresh interpreter and reports what it found.
INDEX = """
import json, sys, function_app
heavy = ["duckdb", "numpy", "PIL", "azure.identity", "azure.storage.blob"]
functions = function_app.app.get_functions()
print(json.dumps({
    "timers": {f.get_function_name(): f.get_trigger().schedule for f in functions},
    "monitored": {f.get_function_name(): f.get_trigger().use_monitor for f in functions},
    "heavy": [m for m in heavy if m in sys.modules],
}))
"""


def index(timers_enabled: str | None) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "TIMERS_ENABLED"}
    if timers_enabled is not None:
        env["TIMERS_ENABLED"] = timers_enabled
    out = subprocess.run(
        [sys.executable, "-c", INDEX],
        cwd=PIPELINE,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def test_five_timers_when_enabled():
    found = index("true")
    assert found["timers"] == {
        "radar": "0 4,9,14,19,24,29,34,39,44,49,54,59 * * * *",
        "metar": "0 7,37 * * * *",
        "hourly": "0 45 * * * *",
        "arpa": "0 40 2,5,8,11,14,17,20,23 * * *",
        "nightly": "0 30 1 * * *",
    }
    # Radar and METAR catch up by themselves; the others keep the host's schedule record.
    assert found["monitored"] == {
        "radar": False,
        "metar": False,
        "hourly": None,
        "arpa": None,
        "nightly": None,
    }


def test_no_timer_at_all_unless_enabled():
    assert index(None)["timers"] == {}
    assert index("false")["timers"] == {}
    assert index("True")["timers"] == {}


def test_indexing_leaves_the_heavy_libraries_for_the_jobs():
    assert index("true")["heavy"] == []


def test_towns_are_found_from_a_checkout():
    import function_app

    assert (function_app.TOWNS / "pedrengo.toml").is_file()
