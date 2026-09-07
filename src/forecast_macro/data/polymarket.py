from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from forecast_macro.contracts import OutcomeQuote
from forecast_macro.market_discovery import MarketCandidate, polymarket_candidates

POLYMARKET_CLOB_URL = "https://clob.polymarket.com"
POLYMARKET_GAMMA_URL = "https://gamma-api.polymarket.com"


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


class PolymarketPublicClient:
    def __init__(self, *, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def orderbook(self, token_id: str) -> OutcomeQuote:
        response = httpx.get(
            f"{POLYMARKET_CLOB_URL}/book",
            params={"token_id": token_id},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return parse_polymarket_orderbook(
            response.json(), token_id=token_id, observed_at=datetime.now(UTC)
        )

    def search_macro_markets(self, query: str) -> list[MarketCandidate]:
        response = httpx.get(
            f"{POLYMARKET_GAMMA_URL}/public-search",
            params={"q": query},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return polymarket_candidates(response.json())
