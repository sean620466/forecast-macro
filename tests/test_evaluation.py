from datetime import UTC, datetime, timedelta

import pytest

from forecast_macro.backtest import TimedRow, available_rows, expanding_window_splits
from forecast_macro.evaluation import (
    ForecastRecord,
    brier_score,
    calibration_table,
    expected_calibration_error,
)


def record(probability: float, outcome: int, day: int = 1) -> ForecastRecord:
    forecast_at = datetime(2026, 1, day, tzinfo=UTC)
    return ForecastRecord(
        forecast_at=forecast_at,
        outcome_at=forecast_at + timedelta(days=1),
        probability=probability,
        outcome=outcome,
    )


def test_brier_score_matches_manual_calculation():
    rows = [record(0.8, 1), record(0.3, 0, 2)]
    assert brier_score(rows) == pytest.approx((0.2**2 + 0.3**2) / 2)


def test_calibration_includes_probability_one():
    rows = [record(1.0, 1), record(0.0, 0, 2)]
    table = calibration_table(rows, bins=2)
    assert sum(item.count for item in table) == 2
    assert expected_calibration_error(rows, bins=2) == pytest.approx(0.0)


def test_forecast_rejects_information_after_outcome():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="earlier"):
        ForecastRecord(now, now, 0.5, 1)


def test_available_rows_blocks_future_release():
    cutoff = datetime(2026, 2, 1, tzinfo=UTC)
    rows = [
        TimedRow(cutoff - timedelta(days=1), 1.0),
        TimedRow(cutoff + timedelta(seconds=1), 2.0),
    ]
    assert available_rows(rows, as_of=cutoff) == [rows[0]]


def test_expanding_window_is_strictly_chronological():
    dates = [datetime(2025, month, 1, tzinfo=UTC) for month in range(1, 7)]
    splits = expanding_window_splits(dates, minimum_train_size=3, test_size=1)
    assert len(splits) == 3
    assert splits[0].train_indices == (0, 1, 2)
    assert splits[0].test_indices == (3,)
    assert max(splits[-1].train_indices) < min(splits[-1].test_indices)


def test_expanding_window_rejects_unsorted_dates():
    dates = [datetime(2026, 2, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)]
    with pytest.raises(ValueError, match="sorted"):
        expanding_window_splits(dates, minimum_train_size=1)
