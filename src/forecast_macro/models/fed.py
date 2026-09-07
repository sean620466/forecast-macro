from __future__ import annotations

import math

from forecast_macro.types import Probability


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


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
    cut = _sigmoid(score)
    hold = 1.0 - cut
    return [
        Probability("cut", round(cut, 6)),
        Probability("hold_or_hike", round(hold, 6)),
    ]
