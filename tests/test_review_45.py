"""Task 45: dry run of the scoring and alert path on every real comparison record in the repository.

The first live scoring is the 2026-09-11 CPI release. This test feeds the committed records a
synthetic realized value and checks that every record (Polymarket bucket titles, Kalshi ladder
keys, core and headline CPI, unemployment) parses, scores, and renders an alert body.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from forecast_macro.alerts import TOPICS, build_scoring_alerts
from forecast_macro.unemployment_scoring import (
    final_record_per_release,
    score_unemployment_comparisons,
)

ROOT = Path(__file__).resolve().parents[1]
DIRS = {
    "unemployment": "unemployment_market_comparisons",
    "core_cpi": "core_cpi_market_comparisons",
    "headline_cpi": "headline_cpi_market_comparisons",
}


def _records(directory: str) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted((ROOT / "data" / "generated" / directory).glob("*.json"))]


@pytest.mark.parametrize("topic, directory", list(DIRS.items()))
def test_every_committed_record_scores_and_alerts(topic: str, directory: str) -> None:
    records = _records(directory)
    if not records:
        pytest.skip(f"no {topic} records committed yet")
    finals = final_record_per_release(records)
    assert finals, "no record precedes its release"
    for (period, venue), record in finals.items():
        assert record["venue"] == venue and record["reference_period"] == period
        assert datetime.fromisoformat(record["as_of"]) < datetime.fromisoformat(record["release_at"])
        assert abs(sum(record["model"].values()) - 1.0) < 1e-6
        assert set(record["model"]) == set(record["market"]) == set(record["bucket_titles"])
    realized = {period: float(record["latest_rate"]) for (period, _v), record in finals.items()}
    card = score_unemployment_comparisons(records, realized=realized)
    assert card.scored_releases == len(finals)
    assert {(r.reference_period, r.venue) for r in card.records} == set(finals)
    for row in card.records:
        assert 0.0 <= row.model_probability_of_realized <= 1.0
        assert 0.0 <= row.model_brier <= 2.0 and 0.0 <= row.market_brier <= 2.0
    alerts = build_scoring_alerts({topic: None}, {topic: card.to_dict()}, run_url="https://example/run")
    assert len(alerts) == 1
    body = alerts[0].body
    assert TOPICS[topic].label in alerts[0].title
    for (period, venue) in finals:
        assert f"기준월 {period} · {venue}" in body
    assert "signal_eligible: `False`" in body
