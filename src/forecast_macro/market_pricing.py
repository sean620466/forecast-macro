from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from forecast_macro.contracts import OutcomeQuote, normalize_outcome_prices
from forecast_macro.market_discovery import MarketCandidate
from forecast_macro.market_review import CandidateReview, ReviewStatus


@dataclass(frozen=True)
class EventPriceSnapshot:
    venue: str
    venue_event_id: str
    observed_at: datetime
    probabilities: dict[str, float]
    source_mid_prices: dict[str, float]
    rules_text_hashes: dict[str, str]


def build_event_price_snapshot(
    candidates: Sequence[MarketCandidate],
    reviews: Mapping[str, CandidateReview],
    quotes: Mapping[str, OutcomeQuote],
    rules_text_hashes: Mapping[str, str],
    *,
    as_of: datetime,
    max_spread: float = 0.10,
    min_top_size: float = 1.0,
    max_age: timedelta = timedelta(minutes=2),
    max_timestamp_skew: timedelta = timedelta(seconds=5),
) -> EventPriceSnapshot:
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    if len(candidates) < 2:
        raise ValueError("a complete event requires at least two candidate markets")
    venue_ids = {(candidate.venue, candidate.venue_event_id) for candidate in candidates}
    if len(venue_ids) != 1:
        raise ValueError("all candidates must belong to one venue event")
    venue, event_id = next(iter(venue_ids))
    if not event_id:
        raise ValueError("venue_event_id is required")

    mids: dict[str, float] = {}
    hashes: dict[str, str] = {}
    timestamps: list[datetime] = []
    for candidate in candidates:
        review = reviews.get(candidate.venue_market_id)
        if review is None or review.status is not ReviewStatus.APPROVED:
            raise ValueError("every event contract must be approved before pricing")
        if tuple(label.lower() for label in candidate.outcome_labels) != ("yes", "no"):
            raise ValueError("event bucket pricing requires YES/NO contracts")
        yes_token = candidate.outcome_token_ids[0]
        quote = quotes.get(yes_token)
        if quote is None:
            raise ValueError("missing YES orderbook quote")
        if quote.ask - quote.bid > max_spread:
            raise ValueError("orderbook spread exceeds limit")
        if min(quote.bid_size, quote.ask_size) < min_top_size:
            raise ValueError("orderbook top-level size is below limit")
        if quote.observed_at > as_of or as_of - quote.observed_at > max_age:
            raise ValueError("orderbook quote is stale or from the future")
        rules_hash = rules_text_hashes.get(candidate.venue_market_id)
        if not rules_hash:
            raise ValueError("approved contract requires a rules hash")
        mids[candidate.venue_market_id] = quote.mid
        hashes[candidate.venue_market_id] = rules_hash
        timestamps.append(quote.observed_at)

    if max(timestamps) - min(timestamps) > max_timestamp_skew:
        raise ValueError("event orderbooks were not observed at the same time")
    probabilities = normalize_outcome_prices(
        mids,
        expected_outcomes=tuple(candidate.venue_market_id for candidate in candidates),
    )
    return EventPriceSnapshot(
        venue=venue,
        venue_event_id=event_id,
        observed_at=max(timestamps),
        probabilities=probabilities,
        source_mid_prices=mids,
        rules_text_hashes=hashes,
    )
