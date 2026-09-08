"""D-017 (same-day release flag) and D-018 (horizon-dependent ladder width)."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from forecast_macro.comparison_scoring import score_comparisons
from forecast_macro.contracts import normalize_threshold_ladder
from forecast_macro.datasets import load_fomc_history, scheduled_meetings
from forecast_macro.live_comparison import market_cut_probability, same_day_releases
from forecast_macro.price_snapshots import ladder_width_limit
from forecast_macro.release_schedule import ScheduledRelease, load_release_schedule

ROOT = Path(__file__).parents[1]
ET = "America/New_York"


def test_ladder_width_limit_grows_with_horizon_and_caps() -> None:
    now = datetime(2026, 9, 8, tzinfo=UTC)
    assert ladder_width_limit(now, None) == 0.35
    assert ladder_width_limit(now, datetime(2026, 9, 16, tzinfo=UTC)) == 0.35
    assert ladder_width_limit(now, datetime(2026, 12, 9, tzinfo=UTC)) == pytest.approx(0.40)  # 3 months
    assert ladder_width_limit(now, datetime(2027, 4, 28, tzinfo=UTC)) == pytest.approx(0.60)  # 7 months -> cap
    assert ladder_width_limit(now, datetime(2037, 1, 1, tzinfo=UTC)) == 0.60


def test_wide_far_dated_ladder_prices_under_relaxed_limit() -> None:
    # 5-cent spreads on every rung telescope into a ladder width of about 0.48.
    ladder = {3.00: (0.95, 1.00), 3.25: (0.92, 0.97), 3.50: (0.57, 0.62), 3.75: (0.22, 0.27), 4.00: (0.03, 0.08)}
    with pytest.raises(ValueError, match="too wide"):
        normalize_threshold_ladder(ladder)  # default D-015 width 0.35
    result = normalize_threshold_ladder(ladder, max_width=0.60)
    assert sum(result.probabilities.values()) == pytest.approx(1.0)
    assert result.ask_sum - result.bid_sum > 0.35


def test_same_day_release_detection_from_schedule() -> None:
    schedule = load_release_schedule()
    assert same_day_releases(schedule, meeting_date=date(2026, 9, 16)) == []
    synthetic = [
        *schedule,
        ScheduledRelease("cpi", "2026-08", datetime(2026, 9, 16, 8, 30, tzinfo=UTC), "https://www.bls.gov/x", "t"),
    ]
    assert same_day_releases(synthetic, meeting_date=date(2026, 9, 16)) == ["cpi"]


def test_scoring_reports_clean_subset_excluding_flagged_meetings() -> None:
    meetings = scheduled_meetings(load_fomc_history(ROOT / "data" / "fomc_meetings_2019_2026.csv"))

    def record(meeting_date, as_of, logistic, market, *, same_day=False, low_liq=False, rate=4.5):
        return {
            "as_of": as_of, "meeting_date": meeting_date, "event_ticker": "KXFED-TEST",
            "features": {"policy_rate_upper": rate},
            "heuristic_cut": logistic, "logistic_cut": logistic,
            "market": {"probability": market, "lower_bound": market, "upper_bound": market, "low_liquidity": low_liq},
            "same_day_release": same_day,
        }

    records = [
        record("2025-09-17", "2025-09-16T13:40:00+00:00", 0.7, 0.95),
        record("2025-10-29", "2025-10-28T13:40:00+00:00", 0.8, 0.97, same_day=True, rate=4.25),
        record("2025-12-10", "2025-12-09T13:40:00+00:00", 0.6, 0.90, low_liq=True, rate=4.0),
    ]
    card = score_comparisons(records, meetings=meetings)
    assert card.scored_meetings == 3
    assert card.same_day_release_meetings == 1 and card.low_liquidity_meetings == 1
    assert card.clean_meetings == 1
    assert card.clean_logistic_brier == pytest.approx(0.3**2)
    assert card.clean_market_brier == pytest.approx(0.05**2)


def test_market_record_low_liquidity_flag_is_carried() -> None:
    record = {
        "probabilities": {"le_3.50": 0.02, "3.75": 0.4, "4.00": 0.5, "gt_4.00": 0.08},
        "probability_bounds": {"le_3.50": [0, 0.05], "3.75": [0.3, 0.5], "4.00": [0.4, 0.6], "gt_4.00": [0.02, 0.15]},
        "completeness": {"bid_sum": 0.72, "ask_sum": 1.30, "mid_sum": 1.0, "low_liquidity": 1.0},
        "observed_at": "x",
    }
    market = market_cut_probability(record, current_upper=3.75, source_file="f")
    assert market.low_liquidity is True
