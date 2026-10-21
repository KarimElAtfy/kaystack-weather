"""Scores of forecasts against observations, and the guard that keeps the test period
of docs/verification.md closed.

Every score is given the valid times it covers. If any of them falls in the test
period, 2026-01-01 to 2026-10-16, it raises SealedPeriod, unless the call passes
test=True, which the one pre-registered test script alone does.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

import numpy as np

TEST_FIRST = date(2026, 1, 1)
TEST_LAST = date(2026, 10, 16)
# A local day of the test period ends at 00:00 in Rome, 22:00 or 23:00 UTC the day
# before, so an instant is closed when either its UTC day or its local day is a test
# day. Between these two instants, both excluded, one of them is.
_AFTER = datetime(2025, 12, 31, 23, tzinfo=UTC)
_BEFORE = datetime(2026, 10, 17, tzinfo=UTC)

type When = date | datetime


class SealedPeriod(ValueError):
    pass


def sealed(when: When) -> bool:
    """Dates are local days, datetimes instants or interval ends."""
    if isinstance(when, datetime):
        if when.tzinfo is None:
            raise ValueError(f"{when} has no time zone")
        return _AFTER < when < _BEFORE
    return TEST_FIRST <= when <= TEST_LAST


def check_open(valid: Sequence[When], *, test: bool = False) -> None:
    if test:
        return
    closed = [w for w in valid if sealed(w)]
    if closed:
        raise SealedPeriod(f"{len(closed)} valid times in the test period, from {closed[0]}")


@dataclass(frozen=True)
class Errors:
    n: int
    bias: float
    mae: float
    rmse: float


def errors(
    forecast: Sequence[float],
    observed: Sequence[float],
    valid: Sequence[When],
    *,
    test: bool = False,
) -> Errors:
    check_open(valid, test=test)
    error = np.asarray(forecast, dtype=float) - np.asarray(observed, dtype=float)
    if not len(error) == len(valid):
        raise ValueError(f"{len(error)} errors for {len(valid)} valid times")
    return Errors(
        n=len(error),
        bias=float(error.mean()),
        mae=float(np.abs(error).mean()),
        rmse=float(np.sqrt((error**2).mean())),
    )


@dataclass(frozen=True)
class Difference:
    mean: float
    low: float
    high: float
    days: int


def paired_difference(
    a: Sequence[float],
    b: Sequence[float],
    valid: Sequence[When],
    *,
    block_days: int,
    draws: int = 2000,
    seed: int = 0,
    test: bool = False,
) -> Difference:
    """The mean of a - b over the pairs, with a 95 % interval from a moving-block
    bootstrap over whole days. Errors on consecutive days are correlated, so blocks of
    block_days days are drawn with replacement until they cover as many days as the
    sample. A day is the UTC day of an instant, or the local day of a date."""
    check_open(valid, test=test)
    diff = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    if not len(diff) == len(valid):
        raise ValueError(f"{len(diff)} differences for {len(valid)} valid times")
    days = sorted({_day(w) for w in valid})
    index = {d: i for i, d in enumerate(days)}
    which = np.array([index[_day(w)] for w in valid])
    sums = np.bincount(which, weights=diff, minlength=len(days))
    counts = np.bincount(which, minlength=len(days)).astype(float)
    if len(days) < block_days:
        raise ValueError(f"{len(days)} days are fewer than a block of {block_days}")

    rng = np.random.default_rng(seed)
    blocks = -(-len(days) // block_days)
    starts = rng.integers(0, len(days) - block_days + 1, size=(draws, blocks))
    picked = (starts[:, :, None] + np.arange(block_days)).reshape(draws, -1)[:, : len(days)]
    means = sums[picked].sum(axis=1) / counts[picked].sum(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return Difference(float(diff.mean()), float(low), float(high), len(days))


def _day(when: When) -> date:
    return when.astimezone(UTC).date() if isinstance(when, datetime) else when
