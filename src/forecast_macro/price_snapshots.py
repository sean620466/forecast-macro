from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from forecast_macro.contracts import OutcomeQuote
from forecast_macro.market_discovery import MacroTopic, MarketCandidate
from forecast_macro.market_pricing import build_event_price_snapshot
from forecast_macro.market_review import CandidateReview, ReviewStatus


@dataclass(frozen=True)
class EventPriceRecord:
    """One attempt to price an approved event. probabilities is empty when the gate refused."""

    venue: str
    venue_event_id: str
    topic: str
    observed_at: str
    outcome_at: str | None
    contracts: dict[str, str]  # venue_market_id -> title
    probabilities: dict[str, float]
    source_mid_prices: dict[str, float]
    quotes: dict[str, dict[str, float | str]]
    rules_text_hashes: dict[str, str]
    book_updated_at: dict[str, str]
    rejected_reason: str | None
    # D-012: prices are recorded for a future market baseline; nothing here is a signal.
    signal_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def candidate_from_row(row: Mapping[str, Any]) -> MarketCandidate:
    closes_at = row.get("closes_at")
    return MarketCandidate(
        venue=str(row["venue"]),
        venue_market_id=str(row["venue_market_id"]),
        venue_event_id=str(row["venue_event_id"]) if row.get("venue_event_id") else None,
        title=str(row.get("title", "")),
        topic=MacroTopic(str(row["topic"])),
        closes_at=datetime.fromisoformat(str(closes_at)) if closes_at else None,
        outcome_labels=tuple(str(v) for v in row.get("outcome_labels", ())),
        outcome_token_ids=tuple(str(v) for v in row.get("outcome_token_ids", ())),
        match_basis=str(row.get("match_basis", "")),
        requires_review=bool(row.get("requires_review", True)),
        close_time_verified=bool(row.get("close_time_verified", False)),
        venue_close_raw=row.get("venue_close_raw"),
    )


def review_from_row(row: Mapping[str, Any]) -> CandidateReview:
    return CandidateReview(
        venue=str(row["venue"]),
        venue_event_id=str(row["venue_event_id"]) if row.get("venue_event_id") else None,
        venue_market_id=str(row["venue_market_id"]),
        topic=str(row["topic"]),
        status=ReviewStatus(str(row["status"])),
        checks_passed=tuple(row.get("checks_passed", ())),
        blockers=tuple(row.get("blockers", ())),
    )


def approved_events(
    candidates: Sequence[Mapping[str, Any]], reviews: Sequence[Mapping[str, Any]]
) -> dict[tuple[str, str], list[MarketCandidate]]:
    """Events whose every discovered contract is approved. A partial event is never priced."""
    status_by_market = {
        (str(r["venue"]), str(r["venue_market_id"])): str(r["status"]) for r in reviews
    }
    grouped: dict[tuple[str, str], list[MarketCandidate]] = defaultdict(list)
    for row in candidates:
        if not row.get("venue_event_id"):
            continue
        grouped[(str(row["venue"]), str(row["venue_event_id"]))].append(candidate_from_row(row))
    return {
        key: members
        for key, members in grouped.items()
        if len(members) >= 2
        and all(
            status_by_market.get((m.venue, m.venue_market_id)) == ReviewStatus.APPROVED.value
            for m in members
        )
    }


def price_event(
    members: Sequence[MarketCandidate],
    reviews: Mapping[str, CandidateReview],
    quotes: Mapping[str, OutcomeQuote],
    rules_text_hashes: Mapping[str, str],
    *,
    as_of: datetime,
    outcome_at: datetime | None,
    book_updated_at: Mapping[str, datetime] | None = None,
) -> EventPriceRecord:
    venue = members[0].venue
    event_id = members[0].venue_event_id or ""
    yes_tokens = {m.venue_market_id: m.outcome_token_ids[0] for m in members if m.outcome_token_ids}
    quote_rows: dict[str, dict[str, float | str]] = {}
    for market_id, token in yes_tokens.items():
        quote = quotes.get(token)
        if quote is None:
            continue
        quote_rows[market_id] = {
            "token_id": token,
            "bid": quote.bid,
            "ask": quote.ask,
            "mid": quote.mid,
            "bid_size": quote.bid_size,
            "ask_size": quote.ask_size,
            "tick_size": quote.tick_size,
        }
    updated = {
        market_id: (book_updated_at or {}).get(token).isoformat()  # type: ignore[union-attr]
        for market_id, token in yes_tokens.items()
        if (book_updated_at or {}).get(token) is not None
    }
    base = {
        "venue": venue,
        "venue_event_id": event_id,
        "topic": members[0].topic.value,
        "observed_at": as_of.isoformat(),
        "outcome_at": outcome_at.isoformat() if outcome_at else None,
        "contracts": {m.venue_market_id: m.title for m in members},
        "quotes": quote_rows,
        "rules_text_hashes": {
            m.venue_market_id: rules_text_hashes.get(m.venue_market_id, "") for m in members
        },
        "book_updated_at": updated,
    }
    try:
        snapshot = build_event_price_snapshot(
            members, reviews, quotes, rules_text_hashes, as_of=as_of
        )
    except ValueError as error:
        return EventPriceRecord(
            **base, probabilities={}, source_mid_prices={}, rejected_reason=str(error)
        )
    return EventPriceRecord(
        **base,
        probabilities=snapshot.probabilities,
        source_mid_prices=snapshot.source_mid_prices,
        rejected_reason=None,
    )
