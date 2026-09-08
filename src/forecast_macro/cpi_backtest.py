"""Research backtest of the two CPI YoY baselines on published index levels (task 41).

For every target month, both models see the levels through the month before and predict the
published YoY on a fixed tenth-point bucket grid centred on the latest YoY (the shape of the
Polymarket and Kalshi contracts). Scores are the multi-class Brier and the probability given
to the realized bucket. No market prices are involved (D-007 stays untouched); this decides
only which baseline is the better research reference.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import date

from forecast_macro.models.core_cpi import core_cpi_yoy_history
from forecast_macro.models.cpi_base_effect import MODEL_VERSION as BASE_EFFECT_VERSION
from forecast_macro.models.cpi_base_effect import (
    SAME_MONTH_MODEL_VERSION,
    base_effect_yoy_distribution,
    published_yoy,
)
from forecast_macro.models.unemployment import (
    MonthlyRate,
    RateBucket,
    _tenth,
    monthly_change_distribution,
    next_month_bucket_probabilities,
)

EMPIRICAL_CHANGE_VERSION = "cpi-yoy-empirical-change-0.1-uncalibrated"
HALF_WIDTH_TENTHS = 4  # buckets: <= latest-0.4, latest-0.3 ... latest+0.3, >= latest+0.4


@dataclass(frozen=True)
class MonthScore:
    target_month: str
    latest_yoy: float
    realized_yoy: float
    realized_bucket: str
    empirical_change_brier: float
    base_effect_brier: float
    empirical_change_p_realized: float
    base_effect_p_realized: float
    base_effect_mode: float
    same_month_brier: float = 0.0
    same_month_p_realized: float = 0.0


@dataclass(frozen=True)
class CpiBaselineBacktest:
    series_id: str
    start: str
    end: str
    months: int
    empirical_change_brier: float | None
    base_effect_brier: float | None
    base_effect_skill_vs_empirical_change: float | None
    empirical_change_mean_p_realized: float | None
    base_effect_mean_p_realized: float | None
    base_effect_wins: int
    empirical_change_wins: int
    # Same-month-only variant, reported for transparency (coarser, ~25 samples per month).
    same_month_brier: float | None = None
    same_month_skill_vs_empirical_change: float | None = None
    empirical_change_version: str = EMPIRICAL_CHANGE_VERSION
    base_effect_version: str = BASE_EFFECT_VERSION
    same_month_version: str = SAME_MONTH_MODEL_VERSION
    signal_eligible: bool = False
    records: list[MonthScore] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def bucket_grid(latest_yoy: float, half_width: int = HALF_WIDTH_TENTHS) -> list[RateBucket]:
    lower = _tenth(latest_yoy - half_width / 10)
    upper = _tenth(latest_yoy + half_width / 10)
    buckets = [RateBucket(key=f"le_{lower:.1f}", kind="lower", value=lower)]
    for step in range(-half_width + 1, half_width):
        value = _tenth(latest_yoy + step / 10)
        buckets.append(RateBucket(key=f"{value:.1f}", kind="exact", value=value))
    buckets.append(RateBucket(key=f"ge_{upper:.1f}", kind="upper", value=upper))
    return buckets


def _brier(probabilities: dict[str, float], realized_key: str) -> float:
    return sum((p - float(key == realized_key)) ** 2 for key, p in probabilities.items())


def backtest_cpi_baselines(
    levels: Sequence[MonthlyRate],
    *,
    series_id: str,
    start: date,
    end: date | None = None,
    history_start: date | None = None,
) -> CpiBaselineBacktest:
    rows = sorted(levels, key=lambda r: r.month)
    by_index = {r.month.year * 12 + r.month.month: r.value for r in rows}
    records: list[MonthScore] = []
    for position, row in enumerate(rows):
        target = row.month
        if target < start or (end is not None and target > end):
            continue
        visible = rows[:position]  # levels through the month before the target
        if len(visible) < 24:
            continue
        realized = published_yoy(by_index, target)
        if realized is None:
            continue
        yoy_history = core_cpi_yoy_history(visible)
        if len(yoy_history) < 24:
            continue
        latest_yoy = yoy_history[-1].value
        buckets = bucket_grid(latest_yoy)
        try:
            change_distribution = monthly_change_distribution(yoy_history, start=history_start)
            empirical = {
                p.outcome: p.probability
                for p in next_month_bucket_probabilities(latest_yoy, change_distribution, buckets)
            }
            predicted_target, base_distribution = base_effect_yoy_distribution(visible, start=history_start)
            _t, same_month_distribution = base_effect_yoy_distribution(visible, start=history_start, method="same_month")
        except ValueError:
            continue
        if predicted_target != target:
            continue  # a gap in the levels (never published month); skip rather than bridge
        base = {p.outcome: p.probability for p in next_month_bucket_probabilities(0.0, base_distribution, buckets)}
        same = {p.outcome: p.probability for p in next_month_bucket_probabilities(0.0, same_month_distribution, buckets)}
        realized_key = next(b.key for b in buckets if b.contains(realized))
        records.append(
            MonthScore(
                target_month=target.isoformat()[:7],
                latest_yoy=latest_yoy,
                realized_yoy=realized,
                realized_bucket=realized_key,
                empirical_change_brier=_brier(empirical, realized_key),
                base_effect_brier=_brier(base, realized_key),
                empirical_change_p_realized=empirical[realized_key],
                base_effect_p_realized=base[realized_key],
                base_effect_mode=max(base_distribution, key=base_distribution.get),
                same_month_brier=_brier(same, realized_key),
                same_month_p_realized=same[realized_key],
            )
        )
    n = len(records)
    mean = lambda values: (sum(values) / n) if n else None
    e_brier = mean([r.empirical_change_brier for r in records])
    b_brier = mean([r.base_effect_brier for r in records])
    s_brier = mean([r.same_month_brier for r in records])
    return CpiBaselineBacktest(
        series_id=series_id,
        start=start.isoformat(),
        end=(end or (rows[-1].month if rows else start)).isoformat(),
        months=n,
        empirical_change_brier=e_brier,
        base_effect_brier=b_brier,
        base_effect_skill_vs_empirical_change=(1.0 - b_brier / e_brier) if e_brier else None,
        empirical_change_mean_p_realized=mean([r.empirical_change_p_realized for r in records]),
        base_effect_mean_p_realized=mean([r.base_effect_p_realized for r in records]),
        base_effect_wins=sum(r.base_effect_brier < r.empirical_change_brier for r in records),
        empirical_change_wins=sum(r.empirical_change_brier < r.base_effect_brier for r in records),
        same_month_brier=s_brier,
        same_month_skill_vs_empirical_change=(1.0 - s_brier / e_brier) if e_brier else None,
        records=records,
    )
