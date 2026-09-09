from __future__ import annotations

import math

from forecast_macro.types import Probability

PROBABILITY_EPSILON = 1e-6
ZLB_UPPER_BOUND = 0.25
ZLB_CUT_PROBABILITY = 0.005


def _sigmoid(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("model inputs must be finite")
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def apply_cut_feasibility(probability: float, *, policy_rate: float) -> float:
    if not math.isfinite(probability) or not math.isfinite(policy_rate):
        raise ValueError("model inputs must be finite")
    if policy_rate <= ZLB_UPPER_BOUND:
        return ZLB_CUT_PROBABILITY
    return min(max(probability, PROBABILITY_EPSILON), 1.0 - PROBABILITY_EPSILON)


def _cut_score(
    inflation_yoy: float,
    unemployment_rate: float,
    unemployment_change_3m: float,
    policy_rate: float,
    neutral_rate: float,
) -> float:
    return (
        -0.9 * (inflation_yoy - 2.0)
        + 1.2 * unemployment_change_3m
        + 0.35 * (unemployment_rate - 4.0)
        + 0.25 * (policy_rate - neutral_rate)
        - 0.5
    )


def _hike_score(
    inflation_yoy: float,
    unemployment_rate: float,
    unemployment_change_3m: float,
    policy_rate: float,
    neutral_rate: float,
) -> float:
    # Mirror image of the cut score: hot inflation and a tightening labour market argue for
    # a hike, a policy rate already above neutral argues against one.
    return (
        0.9 * (inflation_yoy - 2.0)
        - 1.2 * unemployment_change_3m
        - 0.35 * (unemployment_rate - 4.0)
        - 0.25 * (policy_rate - neutral_rate)
        - 0.5
    )


def split_remainder(cut: float, hike_given_no_cut: float) -> tuple[float, float, float]:
    """Nest a binary cut model inside a three-way space (D-016).

    P(cut) is untouched; the remainder is split by the conditional hike probability, so the
    cut component of the three-way vector equals the binary model exactly.
    """
    if not (0.0 <= cut <= 1.0 and 0.0 <= hike_given_no_cut <= 1.0):
        raise ValueError("probabilities must be between 0 and 1")
    remainder = 1.0 - cut
    hike = remainder * hike_given_no_cut
    hold = remainder - hike
    return cut, hold, hike


def rate_decision_probabilities(
    *,
    inflation_yoy: float,
    unemployment_rate: float,
    unemployment_change_3m: float,
    policy_rate: float,
    neutral_rate: float = 2.75,
    hike_given_no_cut: float | None = None,
) -> list[Probability]:
    """Baseline heuristic over cut / hold / hike; coefficients are uncalibrated (D-016).

    `hike_given_no_cut` replaces the mirrored hike score with an externally supplied
    conditional hike probability. The backtest and the live comparison pass the sequential
    climatology frequency of hikes among non-cut meetings (task 46, R16-M1): the mirrored
    score was an unfounded symmetry assumption and scored worse than climatology. The cut
    component is unchanged either way.
    """
    args = (inflation_yoy, unemployment_rate, unemployment_change_3m, policy_rate, neutral_rate)
    cut = apply_cut_feasibility(_sigmoid(_cut_score(*args)), policy_rate=policy_rate)
    raw_hike = _sigmoid(_hike_score(*args)) if hike_given_no_cut is None else hike_given_no_cut
    hike_given_no_cut = min(max(raw_hike, PROBABILITY_EPSILON), 1.0 - PROBABILITY_EPSILON)
    cut, hold, hike = split_remainder(cut, hike_given_no_cut)
    return [Probability("cut", cut), Probability("hold", hold), Probability("hike", hike)]


def rate_cut_probability(
    *,
    inflation_yoy: float,
    unemployment_rate: float,
    unemployment_change_3m: float,
    policy_rate: float,
    neutral_rate: float = 2.75,
) -> list[Probability]:
    """Binary view of the baseline: cut vs everything else. Kept for the CLI and old tests."""
    three_way = rate_decision_probabilities(
        inflation_yoy=inflation_yoy,
        unemployment_rate=unemployment_rate,
        unemployment_change_3m=unemployment_change_3m,
        policy_rate=policy_rate,
        neutral_rate=neutral_rate,
    )
    cut = next(item.probability for item in three_way if item.outcome == "cut")
    return [Probability("cut", cut), Probability("hold_or_hike", 1.0 - cut)]
