"""Task 08: price snapshots for fully approved events."""

from datetime import UTC, datetime, timedelta

from forecast_macro.contracts import OutcomeQuote
from forecast_macro.data.polymarket import book_updated_at, parse_polymarket_orderbooks
from forecast_macro.price_snapshots import approved_events, price_event, review_from_row

NOW = datetime(2026, 9, 8, 2, 0, tzinfo=UTC)
OUTCOME = datetime(2026, 10, 2, 12, 30, tzinfo=UTC)


def _candidate(market_id: str, event: str = "e1", *, topic: str = "unemployment") -> dict:
    return {
        "venue": "polymarket",
        "venue_market_id": market_id,
        "venue_event_id": event,
        "title": f"Will the rate be {market_id}%?",
        "topic": topic,
        "closes_at": "2026-10-02T08:30:00+00:00",
        "outcome_labels": ["Yes", "No"],
        "outcome_token_ids": [f"{market_id}-yes", f"{market_id}-no"],
        "match_basis": "unemployment",
        "close_time_verified": True,
        "venue_close_raw": "2026-10-02T08:30:00Z",
    }


def _review(market_id: str, status: str = "approved", event: str = "e1") -> dict:
    return {
        "venue": "polymarket",
        "venue_event_id": event,
        "venue_market_id": market_id,
        "topic": "unemployment",
        "status": status,
        "checks_passed": [],
        "blockers": [] if status == "approved" else ["x"],
    }


def _quote(token: str, bid: float, ask: float, observed_at: datetime = NOW) -> OutcomeQuote:
    return OutcomeQuote(token, bid, ask, 10, 10, observed_at, 0.01, "polymarket-current-unknown", "polymarket")


def test_only_fully_approved_events_are_selected() -> None:
    candidates = [_candidate("a"), _candidate("b"), _candidate("c", "e2"), _candidate("d", "e2")]
    reviews = [_review("a"), _review("b"), _review("c"), _review("d", "structure_valid_rules_required", "e2")]
    events = approved_events(candidates, reviews)
    assert set(events) == {("polymarket", "e1")}
    assert [m.venue_market_id for m in events[("polymarket", "e1")]] == ["a", "b"]


def test_single_contract_event_is_not_priced() -> None:
    assert approved_events([_candidate("a")], [_review("a")]) == {}


def test_priced_event_records_probabilities_and_provenance() -> None:
    members = approved_events([_candidate("a"), _candidate("b")], [_review("a"), _review("b")])[
        ("polymarket", "e1")
    ]
    reviews = {m: review_from_row(_review(m)) for m in ("a", "b")}
    quotes = {"a-yes": _quote("a-yes", 0.38, 0.40), "b-yes": _quote("b-yes", 0.60, 0.62)}
    record = price_event(
        members,
        reviews,
        quotes,
        {"a": "sha256:a", "b": "sha256:b"},
        as_of=NOW,
        outcome_at=OUTCOME,
        book_updated_at={"a-yes": NOW - timedelta(minutes=3), "b-yes": NOW},
    )
    assert record.rejected_reason is None
    assert sum(record.probabilities.values()) == 1.0
    assert record.source_mid_prices == {"a": 0.39, "b": 0.61}
    assert record.quotes["a"]["bid"] == 0.38
    assert record.book_updated_at["a"] == (NOW - timedelta(minutes=3)).isoformat()
    assert record.outcome_at == OUTCOME.isoformat()
    assert record.signal_eligible is False


def test_gate_refusal_is_recorded_not_raised() -> None:
    members = approved_events([_candidate("a"), _candidate("b")], [_review("a"), _review("b")])[
        ("polymarket", "e1")
    ]
    reviews = {m: review_from_row(_review(m)) for m in ("a", "b")}
    wide = {"a-yes": _quote("a-yes", 0.10, 0.40), "b-yes": _quote("b-yes", 0.60, 0.62)}
    record = price_event(members, reviews, wide, {"a": "h", "b": "h"}, as_of=NOW, outcome_at=OUTCOME)
    assert record.probabilities == {}
    assert record.rejected_reason is not None and "spread" in record.rejected_reason
    assert record.quotes["a"]["ask"] == 0.40  # raw quotes are still kept for the record


def test_batch_books_share_the_fetch_time_but_keep_their_own_update_time() -> None:
    payload = [
        {
            "asset_id": "a-yes",
            "timestamp": "1788832064257",
            "tick_size": "0.01",
            "bids": [{"price": "0.38", "size": "10"}],
            "asks": [{"price": "0.40", "size": "10"}],
        },
        {
            "asset_id": "b-yes",
            "timestamp": "1788832083281",
            "tick_size": "0.01",
            "bids": [{"price": "0.60", "size": "10"}],
            "asks": [{"price": "0.62", "size": "10"}],
        },
    ]
    quotes = parse_polymarket_orderbooks(payload, observed_at=NOW)
    assert {q.observed_at for q in quotes.values()} == {NOW}
    updated = book_updated_at(payload)
    assert (updated["b-yes"] - updated["a-yes"]).total_seconds() > 15
    # Without an override the books carry their own timestamps, which differ by 19 seconds.
    own = parse_polymarket_orderbooks(payload)
    assert own["a-yes"].observed_at != own["b-yes"].observed_at
