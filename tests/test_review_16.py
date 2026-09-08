"""D-016: three-way (cut / hold / hike) Fed outcome space nested on the binary cut model."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from forecast_macro.datasets import load_fomc_history, scheduled_meetings
from forecast_macro.fed_backtest import run_fed_baseline_backtest
from forecast_macro.fed_model_comparison import run_walk_forward_logistic
from forecast_macro.live_comparison import (
    build_comparison,
    market_cut_probability,
    model_three_way_probabilities,
    next_scheduled_meeting,
)
from forecast_macro.models.fed import rate_cut_probability, rate_decision_probabilities
from forecast_macro.release_schedule import load_release_schedule
from forecast_macro.snapshots import HistoricalFeatureSnapshot

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    "inflation, unemployment, change, rate",
    [(2.5, 4.2, 0.2, 4.5), (4.3, 4.3, -0.1, 3.75), (-1.0, 12.0, 8.0, 0.25), (9.0, 3.6, -0.2, 1.0)],
)
def test_three_way_sums_to_one_and_nests_the_binary_cut(inflation, unemployment, change, rate) -> None:
    kwargs = {"inflation_yoy": inflation, "unemployment_rate": unemployment, "unemployment_change_3m": change, "policy_rate": rate}
    three = {p.outcome: p.probability for p in rate_decision_probabilities(**kwargs)}
    binary = {p.outcome: p.probability for p in rate_cut_probability(**kwargs)}
    assert set(three) == {"cut", "hold", "hike"}
    assert sum(three.values()) == pytest.approx(1.0, abs=1e-12)
    assert all(0.0 < value < 1.0 for value in three.values())
    assert three["cut"] == binary["cut"]


def test_zlb_masks_cut_but_not_hike() -> None:
    three = {
        p.outcome: p.probability
        for p in rate_decision_probabilities(inflation_yoy=8.0, unemployment_rate=3.8, unemployment_change_3m=-0.3, policy_rate=0.25)
    }
    assert three["cut"] == 0.005
    assert three["hike"] > 0.5  # March 2022 conditions: hot inflation from the ZLB


def test_backtests_report_three_way_metrics_with_cut_unchanged() -> None:
    meetings = load_fomc_history(ROOT / "data" / "fomc_meetings_2019_2026.csv")
    snapshots = json.loads((ROOT / "data" / "generated" / "fomc_feature_snapshots_2019_2026.json").read_text())
    report = run_fed_baseline_backtest(meetings, snapshots)
    assert report.actual_hikes == 11
    for prediction in report.predictions:
        total = prediction.probability_cut + prediction.probability_hold + prediction.probability_hike
        assert total == pytest.approx(1.0, abs=1e-12)
    # Per-meeting three-way squared errors sum to the reported average.
    assert 0.0 < report.hike_brier < 1.0 and 0.0 < report.hold_brier < 1.0
    walk = run_walk_forward_logistic(scheduled_meetings(meetings), snapshots)
    assert walk.actual_hikes == 11
    assert walk.three_way_brier < walk.three_way_climatology_brier  # hikes are learnable
    assert walk.signal_eligible is False


def test_live_comparison_records_three_way_edges() -> None:
    training = scheduled_meetings(load_fomc_history(ROOT / "data" / "fomc_meetings_2019_2026.csv"))
    training_snapshots = json.loads((ROOT / "data" / "generated" / "fomc_feature_snapshots_2019_2026.json").read_text())
    snapshot = HistoricalFeatureSnapshot(
        meeting_date="2026-09-16", vintage_date="2026-09-07", cpi_yoy_nsa=3.36,
        unemployment_rate=4.1, unemployment_change_3m=-0.2, policy_rate_upper=3.75,
        source_series={}, data_gaps={"CPIAUCNS": ["2025-10"]},
    )
    heuristic, logistic = model_three_way_probabilities(snapshot, training, training_snapshots)
    assert sum(heuristic.values()) == pytest.approx(1.0) and sum(logistic.values()) == pytest.approx(1.0)
    record = {
        "venue": "kalshi", "venue_event_id": "KXFED-26SEP", "observed_at": "x",
        "probabilities": {"le_2.75": 0.005, "3.00": 0.0, "3.25": 0.0, "3.50": 0.0, "3.75": 0.47, "4.00": 0.51, "4.25": 0.01, "gt_4.25": 0.005},
        "probability_bounds": {"le_2.75": [0, 0.01], "3.00": [0, 0.01], "3.25": [0, 0.01], "3.50": [0, 0.01], "3.75": [0.46, 0.48], "4.00": [0.50, 0.52], "4.25": [0, 0.02], "gt_4.25": [0, 0.01]},
    }
    market = market_cut_probability(record, current_upper=3.75, source_file="f")
    assert (market.probability, market.hold_probability, market.hike_probability) == pytest.approx((0.005, 0.47, 0.525))
    assert market.hike_lower_bound == pytest.approx(0.50) and market.hike_upper_bound == pytest.approx(0.55)
    comparison = build_comparison(
        as_of=datetime(2026, 9, 8, 13, 40, tzinfo=UTC),
        meeting=next_scheduled_meeting(load_release_schedule(), as_of=datetime(2026, 9, 8, tzinfo=UTC)),
        snapshot=snapshot, heuristic_cut=heuristic["cut"], logistic_cut=logistic["cut"],
        training_size=len(training), market=market, heuristic_three_way=heuristic, logistic_three_way=logistic,
    )
    assert comparison.logistic_three_way_edge["hike"] == pytest.approx(logistic["hike"] - 0.525)
    assert comparison.model_version == "fed-live-0.3-three-way-2015-uncalibrated"
    assert comparison.signal_eligible is False
