"""Task 09 / D-015: bucket normalization with probability bounds."""

from datetime import UTC, datetime

import pytest

from forecast_macro.contracts import OutcomeQuote, normalize_bucket_quotes, normalize_outcome_prices
from forecast_macro.market_discovery import MacroTopic, MarketCandidate
from forecast_macro.market_pricing import build_event_price_snapshot
from forecast_macro.market_review import CandidateReview, ReviewStatus

# Live Polymarket YES quotes for event 964993 (September 2026 unemployment), 2026-09-08 01:50 UTC.
LIVE = {
    "le3.8": (0.022, 0.059),
    "3.9": (0.02, 0.07),
    "4.0": (0.17, 0.21),
    "4.1": (0.34, 0.36),
    "4.2": (0.28, 0.30),
    "4.3": (0.11, 0.12),
    "4.4": (0.03, 0.07),
    "4.5": (0.012, 0.048),
    "ge4.6": (0.011, 0.048),
}
NOW = datetime(2026, 9, 8, 1, 50, tzinfo=UTC)


def test_old_mid_rule_rejects_the_live_event_but_d015_prices_it() -> None:
    mids = {k: (b + a) / 2 for k, (b, a) in LIVE.items()}
    with pytest.raises(ValueError, match="too far from a complete market"):
        normalize_outcome_prices(mids)
    result = normalize_bucket_quotes(LIVE)
    assert result.bid_sum == pytest.approx(0.995)
    assert result.ask_sum == pytest.approx(1.285)
    assert result.mid_sum == pytest.approx(1.14)
    assert sum(result.probabilities.values()) == pytest.approx(1.0, abs=1e-12)
    for outcome, (bid, ask) in LIVE.items():
        assert bid <= result.probabilities[outcome] <= ask, outcome
    # The mode is untouched in ranking; the overround is taken mostly from the wide tails.
    assert max(result.probabilities, key=result.probabilities.get) == "4.1"
    assert result.probabilities["4.1"] == pytest.approx(0.35, abs=0.01)
    assert result.probabilities["3.9"] < mids["3.9"]


def test_completeness_gates() -> None:
    with pytest.raises(ValueError, match="bid sum exceeds 1"):
        normalize_bucket_quotes({"a": (0.6, 0.62), "b": (0.5, 0.52)})
    with pytest.raises(ValueError, match="ask sum is below 1"):
        normalize_bucket_quotes({"a": (0.4, 0.42), "b": (0.4, 0.45)})
    with pytest.raises(ValueError, match="too wide"):
        normalize_bucket_quotes({"a": (0.1, 0.5), "b": (0.1, 0.5), "c": (0.1, 0.5)})
    with pytest.raises(ValueError, match="do not match"):
        normalize_bucket_quotes({"a": (0.4, 0.5), "b": (0.5, 0.6)}, expected_outcomes=("a", "c"))
    with pytest.raises(ValueError, match="bid <= ask"):
        normalize_bucket_quotes({"a": (0.5, 0.4), "b": (0.5, 0.6)})


def test_tight_quotes_reduce_to_plain_normalization() -> None:
    result = normalize_bucket_quotes({"a": (0.38, 0.40), "b": (0.60, 0.62)})
    assert result.probabilities == pytest.approx({"a": 0.39, "b": 0.61})
    assert result.lower_bounds == {"a": 0.38, "b": 0.60}


def _candidate(market_id: str, token: str) -> MarketCandidate:
    return MarketCandidate(
        venue="polymarket",
        venue_market_id=market_id,
        venue_event_id="964993",
        title=market_id,
        topic=MacroTopic.UNEMPLOYMENT,
        closes_at=None,
        outcome_labels=("Yes", "No"),
        outcome_token_ids=(token, token + "-no"),
        match_basis="unemployment",
        close_time_verified=True,
    )


def test_event_snapshot_carries_bounds_and_completeness() -> None:
    candidates = [_candidate(k, f"{k}-yes") for k in LIVE]
    reviews = {
        k: CandidateReview("polymarket", "964993", k, "unemployment", ReviewStatus.APPROVED, (), ())
        for k in LIVE
    }
    quotes = {
        f"{k}-yes": OutcomeQuote(f"{k}-yes", b, a, 10, 10, NOW, 0.01, "fees", "polymarket")
        for k, (b, a) in LIVE.items()
    }
    snapshot = build_event_price_snapshot(
        candidates, reviews, quotes, {k: f"sha256:{k}" for k in LIVE}, as_of=NOW
    )
    assert sum(snapshot.probabilities.values()) == pytest.approx(1.0)
    assert snapshot.lower_bounds["4.1"] == 0.34 and snapshot.upper_bounds["4.1"] == 0.36
    assert snapshot.bid_sum == pytest.approx(0.995)
    assert snapshot.mid_sum == pytest.approx(1.14)
