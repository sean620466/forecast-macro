from __future__ import annotations

from collections.abc import Sequence

from forecast_macro.models.unemployment import MonthlyRate, _tenth
from forecast_macro.transforms import percent_change

# One-month-ahead baseline for Core CPI year-over-year buckets (Polymarket "Core CPI YoY").
# The contract settles on the BLS-published 12-month change of CPI-U less food and energy,
# not seasonally adjusted (CPILFENS), rounded to a tenth. The baseline reuses the
# unemployment machinery: next published YoY = latest YoY + an empirical one-month change in
# the YoY series. No tunable parameters (D-005).

MODEL_VERSION = "core-cpi-yoy-empirical-change-0.1-uncalibrated"
SERIES_ID = "CPILFENS"


def core_cpi_yoy_history(levels: Sequence[MonthlyRate]) -> list[MonthlyRate]:
    """Published-style YoY (%) for every month with a level exactly twelve months earlier."""
    by_month = {(row.month.year * 12 + row.month.month): row for row in levels}
    out: list[MonthlyRate] = []
    for index in sorted(by_month):
        base = by_month.get(index - 12)
        current = by_month[index]
        if base is None:
            continue
        out.append(MonthlyRate(month=current.month, value=_tenth(percent_change(current.value, base.value))))
    return out
