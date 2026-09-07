from __future__ import annotations

import math


def percent_change(current: float, previous: float) -> float:
    if not math.isfinite(current) or not math.isfinite(previous):
        raise ValueError("index values must be finite")
    if previous <= 0:
        raise ValueError("previous index value must be positive")
    return (current / previous - 1.0) * 100.0


def month_over_month(index_values: list[float]) -> float:
    """Calculate MoM percent change from [previous_month, current_month]."""
    if len(index_values) != 2:
        raise ValueError("month_over_month requires exactly 2 values")
    return percent_change(index_values[-1], index_values[-2])


def year_over_year(index_values: list[float]) -> float:
    """Calculate YoY percent change from 13 consecutive monthly index values."""
    if len(index_values) != 13:
        raise ValueError("year_over_year requires exactly 13 monthly values")
    return percent_change(index_values[-1], index_values[0])


def rolling_change(values: list[float], *, periods: int) -> float:
    if periods < 1:
        raise ValueError("periods must be positive")
    if len(values) != periods + 1:
        raise ValueError(f"rolling_change requires exactly {periods + 1} values")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("values must be finite")
    return values[-1] - values[0]
