"""CPI YoY baseline with the base effect made explicit (task 41, R35-M1).

A published year-over-year rate for month t+1 is L[t+1] / L[t-11] - 1. When the model runs,
L[t] and L[t-11] are already published, so the only unknown is the next month-over-month
change m[t+1]:

    YoY[t+1] = (L[t] / L[t-11]) * (1 + m[t+1]) - 1

The empirical-change baseline (`core_cpi.py`) ignores this and draws a change in YoY itself,
which mixes the known base effect with the unknown month. This model keeps the base exactly
and draws m[t+1] from the history of the *same calendar month* (NSA indexes are strongly
seasonal: August CPI-U behaves like past Augusts, not like past Januaries). Two ways to draw m[t+1], both untuned (D-005):

* `same_month`: one sample per past year of the target calendar month. Exact seasonality,
  but only ~25 samples, so the distribution is coarse on a tenth-point grid.
* `pooled` (default): the target month's historical mean MoM plus a residual drawn from every
  month's deviation from its own calendar-month mean. Same seasonal level, ~300 residual
  samples. This is the classical seasonal-mean decomposition, not a fitted parameter.

NSA index levels are never revised, so a current-vintage history is point-in-time here.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date

from forecast_macro.models.unemployment import (
    MonthlyRate,
    RateBucket,
    _tenth,
    next_month_bucket_probabilities,
)
from forecast_macro.types import Probability

MODEL_VERSION = "cpi-yoy-base-effect-pooled-mom-0.1-uncalibrated"
SAME_MONTH_MODEL_VERSION = "cpi-yoy-base-effect-same-month-mom-0.1-uncalibrated"
MINIMUM_YEARS = 10
METHODS = ("pooled", "same_month")


def _index(month: date) -> int:
    return month.year * 12 + month.month


def next_month(month: date) -> date:
    return date(month.year + (month.month == 12), month.month % 12 + 1, 1)


def published_yoy(levels: Mapping[int, float], month: date) -> float | None:
    base = levels.get(_index(month) - 12)
    current = levels.get(_index(month))
    if base is None or current is None:
        return None
    return _tenth((current / base - 1.0) * 100.0)


def same_month_mom_history(
    levels: Mapping[int, float], *, target: date, start: date | None = None
) -> list[tuple[int, float]]:
    """(year, MoM fraction) for every past year with both the target month and the month before."""
    out: list[tuple[int, float]] = []
    for year in range(1900, target.year):
        if start is not None and date(year, target.month, 1) < start:
            continue
        idx = year * 12 + target.month
        current, previous = levels.get(idx), levels.get(idx - 1)
        if current is None or previous is None:
            continue
        out.append((year, current / previous - 1.0))
    return out


def pooled_mom_samples(
    levels: Mapping[int, float], *, target: date, start: date | None = None
) -> list[float]:
    """Target month's mean MoM plus every month's residual from its own calendar-month mean."""
    by_month: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    for idx in sorted(levels):
        year, month = divmod(idx - 1, 12)
        month += 1
        if date(year, month, 1) >= target:
            continue
        if start is not None and date(year, month, 1) < start:
            continue
        previous = levels.get(idx - 1)
        if previous is None:
            continue
        by_month[month].append(levels[idx] / previous - 1.0)
    means = {m: sum(v) / len(v) for m, v in by_month.items() if v}
    if target.month not in means:
        return []
    residuals = [value - means[m] for m, values in by_month.items() for value in values]
    return [means[target.month] + r for r in residuals]


def base_effect_yoy_distribution(
    history: Sequence[MonthlyRate],
    *,
    start: date | None = None,
    minimum_years: int = MINIMUM_YEARS,
    method: str = "pooled",
) -> tuple[date, dict[float, float]]:
    """Distribution of the next published YoY (tenths) given index levels through the latest month.

    Returns (target month, {yoy: probability}). The base L[t]/L[t-11] is exact; the next MoM
    comes from `method` (see module docstring).
    """
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    if not history:
        raise ValueError("index history is empty")
    rows = sorted(history, key=lambda r: r.month)
    levels = {_index(r.month): r.value for r in rows}
    latest = rows[-1].month
    target = next_month(latest)
    base_level = levels.get(_index(latest) - 11)
    if base_level is None:
        raise ValueError("need the index level eleven months before the latest month")
    yearly = same_month_mom_history(levels, target=target, start=start)
    if len(yearly) < minimum_years:
        raise ValueError(f"need at least {minimum_years} past {target.strftime('%B')}s, have {len(yearly)}")
    samples = [mom for _year, mom in yearly] if method == "same_month" else pooled_mom_samples(levels, target=target, start=start)
    ratio = rows[-1].value / base_level
    counts: Counter[float] = Counter()
    for mom in samples:
        counts[_tenth((ratio * (1.0 + mom) - 1.0) * 100.0)] += 1
    total = sum(counts.values())
    return target, {yoy: count / total for yoy, count in sorted(counts.items())}


def base_effect_bucket_probabilities(
    history: Sequence[MonthlyRate],
    buckets: Sequence[RateBucket],
    *,
    start: date | None = None,
    method: str = "pooled",
) -> list[Probability]:
    """Push the base-effect YoY distribution through published-rounding buckets."""
    _target, distribution = base_effect_yoy_distribution(history, start=start, method=method)
    # The unemployment helper adds `latest + change`; with latest 0 the keys are the YoY values.
    return next_month_bucket_probabilities(0.0, distribution, buckets)
