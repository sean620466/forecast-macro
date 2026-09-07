from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from itertools import pairwise


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


class CpiSeries(StrEnum):
    SA = "CPIAUCSL"
    NSA = "CPIAUCNS"


@dataclass(frozen=True)
class MonthlyIndex:
    month: date
    value: float


def _month_number(value: date) -> int:
    return value.year * 12 + value.month


def validate_consecutive_months(points: list[MonthlyIndex], *, expected: int) -> None:
    if len(points) != expected:
        raise ValueError(f"expected exactly {expected} monthly observations")
    months = [_month_number(point.month) for point in points]
    if any(current - previous != 1 for previous, current in pairwise(months)):
        raise ValueError("monthly observations must be sorted and consecutive")
    if not all(math.isfinite(point.value) and point.value > 0 for point in points):
        raise ValueError("monthly index values must be finite and positive")


def cpi_mom(points: list[MonthlyIndex], *, series_id: str) -> float:
    if series_id != CpiSeries.SA:
        raise ValueError("CPI MoM requires seasonally adjusted CPIAUCSL")
    validate_consecutive_months(points, expected=2)
    return percent_change(points[-1].value, points[0].value)


def cpi_yoy(points: list[MonthlyIndex], *, series_id: str) -> float:
    if series_id != CpiSeries.NSA:
        raise ValueError("CPI YoY requires not-seasonally-adjusted CPIAUCNS")
    validate_consecutive_months(points, expected=13)
    return percent_change(points[-1].value, points[0].value)


def round_bls_tenth(value: float) -> float:
    """Round a published percentage to one decimal using decimal half-up semantics."""
    if not math.isfinite(value):
        raise ValueError("value must be finite")
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
