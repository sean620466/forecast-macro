"""Task 14: scoring recorded comparisons against realized FOMC decisions (D-007 loop)."""

from pathlib import Path

import pytest

from forecast_macro.comparison_scoring import final_record_per_meeting, score_comparisons
from forecast_macro.datasets import load_fomc_history, scheduled_meetings

ROOT = Path(__file__).parents[1]
MEETINGS = scheduled_meetings(load_fomc_history(ROOT / "data" / "fomc_meetings_2019_2026.csv"))


def _record(meeting_date: str, as_of: str, *, heuristic: float, logistic: float, market: float, rate: float = 4.5) -> dict:
    return {
        "as_of": as_of,
        "meeting_date": meeting_date,
        "event_ticker": "KXFED-TEST",
        "features": {"policy_rate_upper": rate},
        "heuristic_cut": heuristic,
        "logistic_cut": logistic,
        "market": {"probability": market, "lower_bound": market - 0.01, "upper_bound": market + 0.01},
        "signal_eligible": False,
    }


def test_last_pre_decision_record_wins_and_post_decision_records_are_ignored() -> None:
    records = [
        _record("2025-09-17", "2025-09-10T13:40:00+00:00", heuristic=0.3, logistic=0.4, market=0.9),
        _record("2025-09-17", "2025-09-16T13:40:00+00:00", heuristic=0.5, logistic=0.6, market=0.95),
        _record("2025-09-17", "2025-09-17T19:00:00+00:00", heuristic=0.99, logistic=0.99, market=0.99),  # after 14:00 ET
        _record("2026-09-16", "2026-09-08T13:40:00+00:00", heuristic=0.1, logistic=0.1, market=0.005),  # future
    ]
    chosen = final_record_per_meeting(records, meetings=MEETINGS)
    assert list(chosen) == ["2025-09-17"]
    assert chosen["2025-09-17"]["logistic_cut"] == 0.6


def test_scorecard_scores_against_realized_cuts_and_keeps_signals_off() -> None:
    # Three late-2025 cuts and one 2026 hold, scored on the day before each decision.
    records = [
        _record("2025-09-17", "2025-09-16T13:40:00+00:00", heuristic=0.6, logistic=0.7, market=0.95),
        _record("2025-10-29", "2025-10-28T13:40:00+00:00", heuristic=0.5, logistic=0.8, market=0.97, rate=4.25),
        _record("2025-12-10", "2025-12-09T13:40:00+00:00", heuristic=0.4, logistic=0.6, market=0.9, rate=4.0),
        _record("2026-01-28", "2026-01-27T13:40:00+00:00", heuristic=0.3, logistic=0.2, market=0.05, rate=3.75),
    ]
    card = score_comparisons(records, meetings=MEETINGS)
    assert card.scored_meetings == 4 and card.non_zlb_meetings == 4
    assert [r.outcome_cut for r in card.records] == [1, 1, 1, 0]
    assert card.market_brier == pytest.approx(((0.05) ** 2 + 0.03**2 + 0.1**2 + 0.05**2) / 4)
    assert card.logistic_brier == pytest.approx((0.3**2 + 0.2**2 + 0.4**2 + 0.2**2) / 4)
    assert card.logistic_skill_vs_market is not None and card.logistic_skill_vs_market < 0
    assert card.sample_gate_passed is False
    assert card.signal_eligible is False
    assert "D-013" in card.signal_eligible_reason


def test_empty_history_scores_nothing() -> None:
    card = score_comparisons([], meetings=MEETINGS)
    assert card.scored_meetings == 0
    assert card.market_brier is None and card.logistic_skill_vs_market is None
    assert card.signal_eligible is False


def test_three_way_scoring_uses_vectors_when_present() -> None:
    record = _record("2025-09-17", "2025-09-16T13:40:00+00:00", heuristic=0.6, logistic=0.7, market=0.95)
    record["heuristic_three_way"] = {"cut": 0.6, "hold": 0.3, "hike": 0.1}
    record["logistic_three_way"] = {"cut": 0.7, "hold": 0.25, "hike": 0.05}
    record["market"].update({"hold_probability": 0.04, "hike_probability": 0.01})
    card = score_comparisons([record], meetings=MEETINGS)
    assert card.three_way_meetings == 1
    assert card.records[0].outcome == "cut"
    assert card.logistic_three_way_brier == pytest.approx(0.3**2 + 0.25**2 + 0.05**2)
    assert card.market_three_way_brier == pytest.approx(0.05**2 + 0.04**2 + 0.01**2)
    assert card.logistic_three_way_skill_vs_market is not None and card.logistic_three_way_skill_vs_market < 0
    # Records without vectors are still scored on the cut component only.
    old = _record("2025-10-29", "2025-10-28T13:40:00+00:00", heuristic=0.5, logistic=0.8, market=0.97, rate=4.25)
    card2 = score_comparisons([record, old], meetings=MEETINGS)
    assert card2.scored_meetings == 2 and card2.three_way_meetings == 1
