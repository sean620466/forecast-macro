from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from forecast_macro.contracts import OutcomeQuote
from forecast_macro.market_discovery import MarketCandidate, polymarket_candidates
from forecast_macro.market_rules import MarketRuleDocument, parse_polymarket_rules

POLYMARKET_CLOB_URL = "https://clob.polymarket.com"
POLYMARKET_GAMMA_URL = "https://gamma-api.polymarket.com"
REQUEST_HEADERS = {"User-Agent": "forecast-macro/0.1 (+https://github.com/sean620466/forecast-macro)"}


def parse_polymarket_orderbook(
    payload: dict[str, Any],
    *,
    token_id: str,
    observed_at: datetime,
) -> OutcomeQuote:
    bids = [(float(level["price"]), float(level["size"])) for level in payload.get("bids", [])]
    asks = [(float(level["price"]), float(level["size"])) for level in payload.get("asks", [])]
    if not bids or not asks:
        raise ValueError("Polymarket orderbook requires bids and asks")
    bid, bid_size = max(bids, key=lambda level: level[0])
    ask, ask_size = min(asks, key=lambda level: level[0])
    return OutcomeQuote(
        outcome_id=token_id,
        bid=bid,
        ask=ask,
        bid_size=bid_size,
        ask_size=ask_size,
        observed_at=observed_at,
        tick_size=float(payload.get("tick_size", 0.001)),
        fee_schedule_id="polymarket-current-unknown",
        venue="polymarket",
        venue_contract_id=str(payload.get("market", "")) or None,
    )


def _clob_timestamp(value: object) -> datetime:
    raw = float(value)
    if raw > 10_000_000_000:
        raw /= 1000
    return datetime.fromtimestamp(raw, tz=UTC)


def parse_polymarket_orderbooks(payload: list[dict[str, Any]]) -> dict[str, OutcomeQuote]:
    quotes: dict[str, OutcomeQuote] = {}
    for book in payload:
        token_id = str(book.get("asset_id") or "")
        if not token_id or token_id in quotes:
            raise ValueError("each Polymarket orderbook requires a unique asset_id")
        quotes[token_id] = parse_polymarket_orderbook(
            book,
            token_id=token_id,
            observed_at=_clob_timestamp(book["timestamp"]),
        )
    return quotes


class PolymarketPublicClient:
    def __init__(self, *, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def orderbook(self, token_id: str) -> OutcomeQuote:
        response = httpx.get(
            f"{POLYMARKET_CLOB_URL}/book",
            params={"token_id": token_id},
            headers=REQUEST_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return parse_polymarket_orderbook(
            response.json(), token_id=token_id, observed_at=datetime.now(UTC)
        )

    def orderbooks(self, token_ids: list[str]) -> dict[str, OutcomeQuote]:
        if not token_ids:
            raise ValueError("at least one token id is required")
        response = httpx.post(
            f"{POLYMARKET_CLOB_URL}/books",
            json=[{"token_id": token_id} for token_id in token_ids],
            headers=REQUEST_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return parse_polymarket_orderbooks(response.json())

    def search_macro_markets(self, query: str) -> list[MarketCandidate]:
        response = httpx.get(
            f"{POLYMARKET_GAMMA_URL}/public-search",
            params={"q": query},
            headers=REQUEST_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return polymarket_candidates(response.json())

    def market_rules(self, market_id: str) -> MarketRuleDocument:
        response = httpx.get(
            f"{POLYMARKET_GAMMA_URL}/markets/{market_id}",
            headers=REQUEST_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return parse_polymarket_rules(response.json())
