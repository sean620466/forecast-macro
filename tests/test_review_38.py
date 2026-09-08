"""Task 38: scoring alerts are derived from the growth of the committed scoring files."""
from __future__ import annotations

from forecast_macro.alerts import (
    TOPICS,
    alert_files,
    build_scoring_alerts,
    new_scored_records,
    scoring_alert,
)


def _fed_scorecard(records):
    return {
        "scored_meetings": len(records),
        "minimum_sample_required": 30,
        "logistic_brier": 0.21,
        "market_brier": 0.19,
        "logistic_skill_vs_market": -0.105,
        "clean_meetings": len(records),
        "clean_logistic_brier": 0.21,
        "clean_market_brier": 0.19,
        "signal_eligible": False,
        "signal_eligible_reason": "sample gate not met (D-013)",
        "records": records,
    }


FED_RECORD = {
    "meeting_date": "2026-09-16",
    "as_of": "2026-09-15T13:44:00+00:00",
    "outcome_cut": 0,
    "outcome": "hold",
    "heuristic_cut": 0.12,
    "logistic_cut": 0.154,
    "market_cut": 0.005,
    "market_lower": 0.0,
    "market_upper": 0.02,
    "policy_rate_upper": 3.75,
    "non_zlb": True,
    "same_day_release": False,
    "low_liquidity": False,
    "logistic_three_way_error": 0.08,
    "market_three_way_error": 0.55,
}


def test_no_alert_when_nothing_new():
    current = _fed_scorecard([FED_RECORD])
    assert scoring_alert(TOPICS["fed"], current, current) is None
    assert new_scored_records(current, current, "meeting_date") == []


def test_first_scored_meeting_raises_one_alert_with_figures():
    previous = _fed_scorecard([])
    current = _fed_scorecard([FED_RECORD])
    alerts = build_scoring_alerts({"fed": previous}, {"fed": current}, run_url="https://example/run/1")
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.title == "[채점] FOMC 금리 결정 2026-09-16: 모델 vs 시장 결과"
    assert "실제 **hold**" in alert.body
    assert "로지스틱 15.4%" in alert.body and "시장 0.5%" in alert.body
    assert "누적 채점: **1건** / 표본 게이트 30건" in alert.body
    assert "signal_eligible: `False`" in alert.body
    assert "https://example/run/1" in alert.body
    files = alert_files(alerts)
    assert set(files) == {"fed.md"}
    assert files["fed.md"].split("\n", 1)[0] == alert.title


def test_missing_previous_file_counts_everything_as_new():
    current = _fed_scorecard([FED_RECORD])
    assert len(new_scored_records(None, current, "meeting_date")) == 1


def test_bucket_topics_use_reference_period():
    record = {
        "reference_period": "2026-09",
        "release_at": "2026-10-02T12:30:00+00:00",
        "as_of": "2026-10-01T13:44:00+00:00",
        "realized_rate": 4.2,
        "realized_bucket": "4.2",
        "model_brier": 0.61,
        "market_brier": 0.70,
        "model_probability_of_realized": 0.27,
        "market_probability_of_realized": 0.22,
    }
    current = {
        "scored_releases": 1,
        "minimum_sample_required": 30,
        "model_brier": 0.61,
        "market_brier": 0.70,
        "model_skill_vs_market": 0.128,
        "signal_eligible": False,
        "signal_eligible_reason": "sample gate not met",
        "records": [record],
    }
    alerts = build_scoring_alerts({"unemployment": None, "core_cpi": None}, {"unemployment": current})
    assert [a.topic for a in alerts] == ["unemployment"]
    assert "기준월 2026-09" in alerts[0].body and "모델 27.0%" in alerts[0].body
