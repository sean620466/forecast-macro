from datetime import UTC, datetime, timedelta

import pytest

from forecast_macro.backtest import ForecastEvent, purged_expanding_window_splits
from forecast_macro.evaluation import (
    ForecastRecord,
    brier_score,
    brier_skill_score,
    calibration_table,
    climatology_probability,
)
from forecast_macro.features import ReleasedValue, build_fomc_snapshot
from forecast_macro.fomc import RateDecision, to_binary_model_outcome


def test_decimal_bin_boundaries_use_their_own_lower_bin():
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [ForecastRecord(base, base + timedelta(days=1), p, 0) for p in [0.1, 0.3, 0.6, 0.7]]
    table = calibration_table(rows, bins=10)
    assert [round(row.lower, 1) for row in table] == [0.1, 0.3, 0.6, 0.7]


def test_purged_split_excludes_unresolved_training_label():
    base = datetime(2026, 1, 1, tzinfo=UTC)
    events = [
        ForecastEvent(base, base + timedelta(days=1)),
        ForecastEvent(base + timedelta(days=2), base + timedelta(days=10)),
        ForecastEvent(base + timedelta(days=3), base + timedelta(days=4)),
    ]
    splits = purged_expanding_window_splits(events, minimum_train_size=1)
    assert splits[-1].train_indices == (0,)


def test_brier_skill_score_against_climatology():
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        ForecastRecord(base, base + timedelta(days=1), 0.8, 1),
        ForecastRecord(base, base + timedelta(days=1), 0.2, 0),
    ]
    climate = climatology_probability(rows)
    baseline = sum((climate - row.outcome) ** 2 for row in rows) / len(rows)
    assert climate == 0.5
    assert brier_skill_score(brier_score(rows), baseline) > 0


def test_vintage_mismatch_is_rejected():
    cutoff = datetime(2026, 6, 1, tzinfo=UTC)
    prior = cutoff - timedelta(days=1)
    with pytest.raises(ValueError, match="vintages must match"):
        build_fomc_snapshot(
            forecast_at=cutoff,
            inflation_yoy=ReleasedValue("inflation_yoy", 2.4, prior, "v1"),
            unemployment_rate=ReleasedValue("unemployment_rate", 4.3, prior, "v1"),
            unemployment_3m_ago=ReleasedValue("unemployment_3m_ago", 4.0, prior, "v2"),
            policy_rate=ReleasedValue("policy_rate", 4.5, prior, "v1"),
        )


def test_rate_decision_binary_mapping():
    assert to_binary_model_outcome(RateDecision.CUT) == "cut"
    assert to_binary_model_outcome(RateDecision.HOLD) == "hold_or_hike"
    assert to_binary_model_outcome(RateDecision.HIKE) == "hold_or_hike"
