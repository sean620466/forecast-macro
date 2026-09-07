from __future__ import annotations

import math

from forecast_macro.types import Probability


def _normal_cdf(value: float, mean: float, std: float) -> float:
    if std <= 0:
        raise ValueError("std must be positive")
    return 0.5 * (1.0 + math.erf((value - mean) / (std * math.sqrt(2.0))))


def cpi_bucket_probabilities(
    *,
    forecast_mom: float,
    uncertainty: float = 0.12,
    lower_cutoff: float = 0.15,
    upper_cutoff: float = 0.35,
) -> list[Probability]:
    """Return probabilities for CPI MoM below/in/above a configured range."""
    below = _normal_cdf(lower_cutoff, forecast_mom, uncertainty)
    at_or_below_upper = _normal_cdf(upper_cutoff, forecast_mom, uncertainty)
    middle = max(0.0, at_or_below_upper - below)
    above = max(0.0, 1.0 - at_or_below_upper)
    total = below + middle + above
    return [
        Probability("below", below / total),
        Probability("in_range", middle / total),
        Probability("above", above / total),
    ]
