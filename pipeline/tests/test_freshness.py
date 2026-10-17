import re
from pathlib import Path

from meteo import status

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "freshness.yml"


def test_the_hourly_probe_uses_the_pipelines_limits():
    # freshness.yml keeps its own copy, so that a broken pipeline cannot loosen the
    # check made from outside Azure. The copies have to stay equal.
    text = WORKFLOW.read_text(encoding="utf-8")
    pattern = r'"([a-z-]+)":\s*\{"data":\s*(\d+),\s*"checked":\s*(\d+)\}'
    limits = {name: (int(data), int(checked)) for name, data, checked in re.findall(pattern, text)}
    assert limits == status.LIMITS
