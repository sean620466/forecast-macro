"""Task 18: scoring unemployment comparisons against first-published rates."""

import pytest

from forecast_macro.unemployment_scoring import (
    final_record_per_release,
    score_unemployment_comparisons,
)

TITLES = {
    "low": "Will the September 2026 unemployment rate be ≤3.8%?",
    "3.9": "Will the September 2026 unemployment rate be 3.9%?",
    "4.0": "Will the September 2026 unemployment rate be 4.0%?",
    "4.1": "Will the September 2026 unemployment rate be 4.1%?",
    "4.2": "Will the September 2026 unemployment rate be 4.2%?",
    "high": "Will the September 2026 unemployment rate be ≥4.3%?",
}


def _record(as_of: str, model: dict, market: dict, period: str = "2026-09") -> dict:
    return {
        "as_of": as_of,
        "release_at": "2026-10-02T08:30:00-04:00",
        "reference_period": period,
        "bucket_titles": TITLES,
        "model": model,
        "market": market,
    }


MODEL = {"low": 0.05, "3.9": 0.10, "4.0": 0.25, "4.1": 0.30, "4.2": 0.20, "high": 0.10}
MARKET = {"low": 0.02, "3.9": 0.03, "4.0": 0.15, "4.1": 0.35, "4.2": 0.30, "high": 0.15}


def test_last_pre_release_record_is_used() -> None:
    records = [
        _record("2026-09-08T13:40:00+00:00", MODEL, MARKET),
        _record("2026-10-01T13:40:00+00:00", MODEL, MARKET),
        _record("2026-10-02T13:00:00+00:00", MODEL, MARKET),  # after 08:30 ET release
    ]
    chosen = final_record_per_release(records)
    # Keyed by (reference period, venue) since task 40: each venue is its own baseline.
    assert [period for period, _venue in chosen] == ["2026-09"]
    assert next(iter(chosen.values()))["as_of"] == "2026-10-01T13:40:00+00:00"


def test_scores_use_first_published_rounded_rate() -> None:
    records = [_record("2026-10-01T13:40:00+00:00", MODEL, MARKET)]
    card = score_unemployment_comparisons(records, realized={"2026-09": 4.24})
    assert card.scored_releases == 1
    row = card.records[0]
    assert row.realized_rate == 4.2 and row.realized_bucket == "4.2"
    assert row.model_brier == pytest.approx(sum((p - (k == "4.2")) ** 2 for k, p in MODEL.items()))
    assert row.market_brier == pytest.approx(sum((p - (k == "4.2")) ** 2 for k, p in MARKET.items()))
    assert card.model_skill_vs_market is not None and card.model_skill_vs_market < 0  # market was closer
    assert card.sample_gate_passed is False and card.signal_eligible is False


def test_tail_realizations_and_missing_labels() -> None:
    records = [_record("2026-10-01T13:40:00+00:00", MODEL, MARKET)]
    card = score_unemployment_comparisons(records, realized={"2026-09": 4.7})
    assert card.records[0].realized_bucket == "high"
    unscored = score_unemployment_comparisons(records, realized={})
    assert unscored.scored_releases == 0 and unscored.model_brier is None
