from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise

from forecast_macro.types import Probability

# Baseline for one-month-ahead unemployment-rate buckets (research only, D-005).
#
# BLS publishes U-3 to one decimal, and bucket contracts settle on that rounded figure. The
# baseline is deliberately nonparametric: the next published rate is the latest rate plus a
# one-month change drawn from the empirical distribution of past one-month changes. There is
# nothing to tune, the 2020 outliers stay in at their historical frequency, and every input
# is point-in-time when the history comes from ALFRED at today's vintage.

MODEL_VERSION = "unemployment-empirical-change-0.1-uncalibrated"


@dataclass(frozen=True)
class MonthlyRate:
    month: date
    value: float


def _tenth(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def monthly_change_distribution(
    history: Sequence[MonthlyRate], *, start: date | None = None
) -> dict[float, float]:
    """Empirical distribution of consecutive-month changes, in tenths of a point.

    Months that were never published (October 2025) simply break the chain: the change
    across the gap is not used, and neither is any synthetic fill.
    """
    rows = sorted((row for row in history if start is None or row.month >= start), key=lambda r: r.month)
    if len(rows) < 24:
        raise ValueError("at least two years of monthly history are required")
    changes: Counter[float] = Counter()
    for previous, current in pairwise(rows):
        months_apart = (current.month.year - previous.month.year) * 12 + (
            current.month.month - previous.month.month
        )
        if months_apart != 1:
            continue
        changes[_tenth(current.value - previous.value)] += 1
    total = sum(changes.values())
    if total == 0:
        raise ValueError("history has no consecutive months")
    return {change: count / total for change, count in sorted(changes.items())}


@dataclass(frozen=True)
class RateBucket:
    key: str
    kind: str  # "lower" (<= value), "exact" (== value), "upper" (>= value)
    value: float

    def contains(self, rate: float) -> bool:
        rounded = _tenth(rate)
        if self.kind == "lower":
            return rounded <= self.value + 1e-9
        if self.kind == "upper":
            return rounded >= self.value - 1e-9
        return abs(rounded - self.value) < 1e-9


def validate_buckets(buckets: Sequence[RateBucket]) -> None:
    kinds = Counter(bucket.kind for bucket in buckets)
    if kinds["lower"] != 1 or kinds["upper"] != 1:
        raise ValueError("bucket set needs exactly one lower tail and one upper tail")
    lower = next(b.value for b in buckets if b.kind == "lower")
    upper = next(b.value for b in buckets if b.kind == "upper")
    exact = sorted(b.value for b in buckets if b.kind == "exact")
    expected = [_tenth(lower + step / 10) for step in range(1, round((upper - lower) * 10))]
    if exact != expected:
        raise ValueError("bucket set is not contiguous in 0.1-point steps")


def next_month_bucket_probabilities(
    latest_rate: float,
    distribution: Mapping[float, float],
    buckets: Sequence[RateBucket],
) -> list[Probability]:
    """Push the empirical change distribution through the published-rounding buckets."""
    validate_buckets(buckets)
    mass = {bucket.key: 0.0 for bucket in buckets}
    for change, probability in distribution.items():
        rate = _tenth(latest_rate + change)
        for bucket in buckets:
            if bucket.contains(rate):
                mass[bucket.key] += probability
                break
    total = sum(mass.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError("buckets do not cover the whole outcome space")
    return [Probability(key, value) for key, value in mass.items()]
