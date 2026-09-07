from __future__ import annotations

import math

from forecast_macro.types import Probability


def _sigmoid(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("model inputs must be finite")
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def rate_cut_probability(
    *,
    inflation_yoy: float,
    unemployment_rate: float,
    unemployment_change_3m: float,
    policy_rate: float,
    neutral_rate: float = 2.75,
) -> list[Probability]:
    """Baseline heuristic model; coefficients must be calibrated on vintage data."""
    score = (
        -0.9 * (inflation_yoy - 2.0)
        + 1.2 * unemployment_change_3m
        + 0.35 * (unemployment_rate - 4.0)
        + 0.25 * (policy_rate - neutral_rate)
        - 0.5
    )
    cut = round(_sigmoid(score), 6)
    hold = 1.0 - cut
    return [
        Probability("cut", cut),
        Probability("hold_or_hike", hold),
    ]
