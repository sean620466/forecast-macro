"""Task 42: input-freshness flag on bucket comparisons (R13-M2) and retirement of the normal-wrapper CPI model."""
from __future__ import annotations

import importlib
from datetime import UTC, datetime

import pytest

from forecast_macro.unemployment_comparison import expected_latest_month
from forecast_macro.unemployment_scoring import (
    final_record_per_release,
    score_unemployment_comparisons,
)


def test_expected_latest_month_wraps_the_year() -> None:
    assert expected_latest_month("2026-09") == "2026-08-01"
    assert expected_latest_month("2027-01") == "2026-12-01"


def _record(as_of: str, latest_month: str, *, inputs_current: bool | None = None) -> dict:
    titles = {"low": "Will the unemployment rate be ≤3.9% in September?", "4.0": "Will the unemployment rate be 4.0% in September?", "high": "Will the unemployment rate be ≥4.1% in September?"}
    row = {
        "as_of": as_of,
        "release_at": "2026-10-02T08:30:00-04:00",
        "reference_period": "2026-09",
        "venue": "polymarket",
        "topic": "unemployment",
        "latest_month": latest_month,
        "bucket_titles": titles,
        "model": {"low": 0.2, "4.0": 0.5, "high": 0.3},
        "market": {"low": 0.1, "4.0": 0.6, "high": 0.3},
    }
    if inputs_current is not None:
        row["inputs_current"] = inputs_current
    return row


def test_stale_input_records_are_never_the_final_record_but_are_counted() -> None:
    records = [
        _record("2026-09-30T13:40:00+00:00", "2026-08-01", inputs_current=True),
        _record("2026-10-01T13:40:00+00:00", "2026-07-01", inputs_current=False),  # ALFRED lag
    ]
    chosen = final_record_per_release(records)
    assert chosen[("2026-09", "polymarket")]["as_of"] == "2026-09-30T13:40:00+00:00"
    card = score_unemployment_comparisons(records, realized={"2026-09": 4.0})
    assert card.scored_releases == 1 and card.stale_input_records == 1
    # Records written before the flag existed are treated as current.
    legacy = [_record("2026-10-01T13:40:00+00:00", "2026-08-01")]
    assert ("2026-09", "polymarket") in final_record_per_release(legacy)


def test_comparison_builder_sets_the_flag_from_the_latest_input_month() -> None:
    from datetime import date

    from forecast_macro.models.unemployment import MonthlyRate
    from forecast_macro.release_schedule import ScheduledRelease
    from forecast_macro.unemployment_comparison import build_unemployment_comparison

    history = [MonthlyRate(month=date(2024 + (i // 12), i % 12 + 1, 1), value=4.0 + (i % 3) * 0.1) for i in range(32)]  # through 2026-08
    keys = ["le_3.90", "4.00", "gt_4.00"]
    record = {
        "venue": "kalshi", "venue_event_id": "KXU3-26SEP", "topic": "unemployment",
        "probabilities": dict.fromkeys(keys, 1 / 3), "probability_bounds": {k: [0.3, 0.4] for k in keys},
        "contracts": {}, "observed_at": "2026-09-08T17:00:00+00:00",
    }
    release = ScheduledRelease(series="employment_situation", reference_period="2026-09", release_at=datetime(2026, 10, 2, 12, 30, tzinfo=UTC), source_url="https://www.bls.gov/schedule", fetched_at="2026-09-08")
    kwargs = {"as_of": datetime(2026, 9, 8, 17, tzinfo=UTC), "release": release, "history_vintage": "2026-09-08", "record": record, "source_file": "x.json"}
    assert build_unemployment_comparison(history=history, **kwargs).inputs_current is True
    assert build_unemployment_comparison(history=history[:-1], **kwargs).inputs_current is False


def test_normal_wrapper_cpi_model_is_gone() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("forecast_macro.models.cpi")
