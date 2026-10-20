from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

from meteo import verify


@pytest.mark.parametrize(
    ("when", "closed"),
    [
        (datetime(2025, 12, 31, 23, tzinfo=UTC), False),
        (datetime(2026, 1, 1, tzinfo=UTC), True),
        (datetime(2026, 7, 1, 12, tzinfo=UTC), True),
        # 01:00 on 17 October in Rome, but still the 16th in UTC.
        (datetime(2026, 10, 16, 23, tzinfo=UTC), True),
        (datetime(2026, 10, 17, tzinfo=UTC), False),
        (date(2025, 12, 31), False),
        (date(2026, 1, 1), True),
        (date(2026, 10, 16), True),
        (date(2026, 10, 17), False),
    ],
)
def test_the_test_period_is_closed_to_scores(when, closed):
    assert verify.sealed(when) is closed
    if closed:
        with pytest.raises(verify.SealedPeriod):
            verify.errors([1.0], [0.0], [when])
    else:
        verify.errors([1.0], [0.0], [when])


def test_the_test_script_may_score_the_test_period():
    scores = verify.errors([1.0], [0.0], [date(2026, 3, 1)], test=True)
    assert scores.n == 1


def test_a_time_without_a_zone_is_refused():
    with pytest.raises(ValueError, match="no time zone"):
        verify.errors([1.0], [0.0], [datetime(2025, 3, 1, 12)])  # noqa: DTZ001


def test_errors():
    scores = verify.errors([1, 2, 3], [0, 2, 5], [date(2025, 5, d) for d in (1, 2, 3)])
    assert (scores.n, scores.mae) == (3, 1.0)
    assert scores.bias == pytest.approx(-1 / 3)
    assert scores.rmse == pytest.approx((5 / 3) ** 0.5)


def test_a_shift_between_two_forecasts_is_found_with_its_interval():
    rng = np.random.default_rng(1)
    days = [date(2025, 1, 1) + timedelta(days=n) for n in range(300)]
    # Errors that persist for days, as weather regimes make them.
    regime = np.repeat(rng.normal(0, 0.5, 60), 5)
    a = np.abs(regime + rng.normal(0, 0.3, 300)) + 0.2
    b = np.abs(regime + rng.normal(0, 0.3, 300))

    shift = verify.paired_difference(a, b, days, block_days=7)
    assert shift.mean == pytest.approx(0.2, abs=0.05)
    assert 0 < shift.low < shift.mean < shift.high
    assert shift.days == 300


def test_several_pairs_on_one_day_count_as_one_day():
    valid = [datetime(2025, 5, 1, h, tzinfo=UTC) for h in range(24)] * 10
    with pytest.raises(ValueError, match="fewer than a block"):
        verify.paired_difference([1.0] * 240, [0.0] * 240, valid, block_days=7)
