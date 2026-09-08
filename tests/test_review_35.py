"""Core CPI YoY bucket baseline (Polymarket 'Core CPI YoY' contracts)."""

from datetime import UTC, date, datetime

import pytest

from forecast_macro.models.core_cpi import MODEL_VERSION, core_cpi_yoy_history
from forecast_macro.models.unemployment import MonthlyRate, monthly_change_distribution
from forecast_macro.release_schedule import load_release_schedule
from forecast_macro.unemployment_comparison import build_unemployment_comparison, next_release

CPI_TITLES = {
    "low": "Will Core CPI YoY be 2.0% or less in August?",
    "2.1": "Will Core CPI YoY be 2.1% in August?",
    "2.2": "Will Core CPI YoY be 2.2% in August?",
    "2.3": "Will Core CPI YoY be 2.3% in August?",
    "high": "Will Core CPI YoY be 2.4% or more in August?",
}


def _levels(start_year: int, months: int, growth: float) -> list[MonthlyRate]:
    rows, value = [], 300.0
    for i in range(months):
        year, month = divmod(start_year * 12 + i, 12)
        value *= 1 + growth
        rows.append(MonthlyRate(month=date(year, month + 1, 1), value=round(value, 3)))
    return rows


def test_yoy_history_is_rounded_published_style_and_needs_twelve_month_base() -> None:
    levels = _levels(2023, 30, 0.0018)  # ~2.2% a year
    history = core_cpi_yoy_history(levels)
    assert len(history) == 18  # first twelve months have no base
    assert history[0].month == date(2024, 1, 1)
    assert all(abs(h.value - 2.2) < 0.11 for h in history)
    assert all(round(h.value, 1) == h.value for h in history)


def test_core_cpi_comparison_uses_the_cpi_calendar_and_contract_buckets() -> None:
    schedule = load_release_schedule()
    as_of = datetime(2026, 9, 8, 13, 40, tzinfo=UTC)
    release = next_release(schedule, as_of=as_of, series="cpi")
    assert release.release_at.isoformat() == "2026-09-11T08:30:00-04:00"
    history = core_cpi_yoy_history(_levels(2022, 55, 0.0018))
    assert monthly_change_distribution(history)
    record = {
        "venue": "polymarket", "venue_event_id": "838712", "topic": "cpi",
        "observed_at": "2026-09-08T12:34:00+00:00", "outcome_at": "2026-09-11T08:30:00-04:00",
        "contracts": CPI_TITLES,
        "probabilities": {"low": 0.1, "2.1": 0.2, "2.2": 0.4, "2.3": 0.2, "high": 0.1},
        "probability_bounds": {k: [0.0, 1.0] for k in CPI_TITLES},
    }
    comparison = build_unemployment_comparison(
        as_of=as_of, release=release, history=history, history_vintage="2026-09-08",
        record=record, source_file="f", model_version=MODEL_VERSION, topic="cpi",
    )
    assert comparison.topic == "cpi" and comparison.model_version == MODEL_VERSION
    assert comparison.reference_period == "2026-08"
    assert sum(comparison.model.values()) == pytest.approx(1.0)
    assert set(comparison.model) == set(CPI_TITLES)
    assert comparison.signal_eligible is False
