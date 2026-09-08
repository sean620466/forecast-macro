from datetime import UTC, datetime, timedelta

import pytest

from forecast_macro.contracts import OutcomeQuote
from forecast_macro.market_discovery import MacroTopic, MarketCandidate
from forecast_macro.market_pricing import build_event_price_snapshot
from forecast_macro.market_review import CandidateReview, ReviewStatus

NOW = datetime(2026, 9, 8, tzinfo=UTC)


def _candidate(market_id: str, token: str) -> MarketCandidate:
    return MarketCandidate(
        venue="polymarket",
        venue_market_id=market_id,
        venue_event_id="event-1",
        title=market_id,
        topic=MacroTopic.CPI,
        closes_at=NOW + timedelta(days=1),
        outcome_labels=("Yes", "No"),
        outcome_token_ids=(token, token + "-no"),
        match_basis="CPI",
    )


def _review(market_id: str, status: ReviewStatus) -> CandidateReview:
    return CandidateReview("polymarket", "event-1", market_id, "cpi", status, (), ())


def _quote(token: str, bid: float, ask: float) -> OutcomeQuote:
    return OutcomeQuote(token, bid, ask, 10, 10, NOW, 0.01, "fees", "polymarket")


def test_only_fully_approved_event_can_produce_prices() -> None:
    candidates = [_candidate("low", "low-yes"), _candidate("high", "high-yes")]
    reviews = {market_id: _review(market_id, ReviewStatus.APPROVED) for market_id in ("low", "high")}
    snapshot = build_event_price_snapshot(
        candidates,
        reviews,
        {"low-yes": _quote("low-yes", 0.38, 0.40), "high-yes": _quote("high-yes", 0.60, 0.62)},
        {"low": "sha256:low", "high": "sha256:high"},
        as_of=NOW,
    )
    assert sum(snapshot.probabilities.values()) == pytest.approx(1.0)
    assert snapshot.probabilities["low"] == pytest.approx(0.39)


def test_pending_contract_keeps_event_locked() -> None:
    candidates = [_candidate("low", "low-yes"), _candidate("high", "high-yes")]
    reviews = {market_id: _review(market_id, ReviewStatus.RULES_REQUIRED) for market_id in ("low", "high")}
    with pytest.raises(ValueError, match="approved"):
        build_event_price_snapshot(candidates, reviews, {}, {}, as_of=NOW)


def test_wide_or_stale_quote_is_rejected() -> None:
    candidates = [_candidate("low", "low-yes"), _candidate("high", "high-yes")]
    reviews = {market_id: _review(market_id, ReviewStatus.APPROVED) for market_id in ("low", "high")}
    quotes = {"low-yes": _quote("low-yes", 0.20, 0.40), "high-yes": _quote("high-yes", 0.58, 0.60)}
    with pytest.raises(ValueError, match="spread"):
        build_event_price_snapshot(
            candidates,
            reviews,
            quotes,
            {"low": "sha256:low", "high": "sha256:high"},
            as_of=NOW,
        )
