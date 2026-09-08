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

# Headline CPI-U (all items, NSA) on the same machinery; Kalshi KXCPIYOY settles on its YoY.
HEADLINE_MODEL_VERSION = "headline-cpi-yoy-empirical-change-0.1-uncalibrated"
HEADLINE_SERIES_ID = "CPIAUCNS"

# Per measure: (FRED level series, model version, contract series named by the rules check,
# comparison directory, file prefix).
CPI_MEASURES: dict[str, tuple[str, str, str, str, str]] = {
    "core": (SERIES_ID, MODEL_VERSION, "core_cpi_yoy_nsa", "core_cpi_market_comparisons", "core_cpi_comparison"),
    "headline": (
        HEADLINE_SERIES_ID,
        HEADLINE_MODEL_VERSION,
        "headline_cpi_yoy_nsa",
        "headline_cpi_market_comparisons",
        "headline_cpi_comparison",
    ),
}


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
