from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from forecast_macro.contracts import OutcomeQuote
from forecast_macro.market_discovery import MarketCandidate, kalshi_candidates

KALSHI_API_URL = "https://external-api.kalshi.com/trade-api/v2"


def _levels(book: dict[str, Any], dollar_key: str, cent_key: str) -> list[tuple[float, float]]:
    raw = book.get(dollar_key)
    divisor = 1.0
    if raw is None:
        raw = book.get(cent_key, [])
        divisor = 100.0
    return [(float(price) / divisor, float(size)) for price, size in raw]


def parse_kalshi_orderbook(
    payload: dict[str, Any],
    *,
    ticker: str,
    observed_at: datetime,
) -> OutcomeQuote:
    book = payload.get("orderbook_fp") or payload.get("orderbook") or payload
    yes = _levels(book, "yes_dollars", "yes")
    no = _levels(book, "no_dollars", "no")
    if not yes or not no:
        raise ValueError("Kalshi orderbook requires both YES and NO bids")
    yes_bid, bid_size = max(yes, key=lambda level: level[0])
    no_bid, ask_size = max(no, key=lambda level: level[0])
    return OutcomeQuote(
        outcome_id="yes",
        bid=yes_bid,
        ask=1.0 - no_bid,
        bid_size=bid_size,
        ask_size=ask_size,
        observed_at=observed_at,
        tick_size=0.01,
        fee_schedule_id="kalshi-current-unknown",
        venue="kalshi",
        venue_contract_id=ticker,
    )


class KalshiPublicClient:
    def __init__(self, *, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def orderbook(self, ticker: str) -> OutcomeQuote:
        response = httpx.get(
            f"{KALSHI_API_URL}/markets/{ticker}/orderbook",
            timeout=self.timeout,
        )
        response.raise_for_status()
        return parse_kalshi_orderbook(
            response.json(), ticker=ticker, observed_at=datetime.now(UTC)
        )

    def discover_open_macro_markets(self) -> list[MarketCandidate]:
        response = httpx.get(
            f"{KALSHI_API_URL}/markets",
            params={"status": "open", "limit": 1000, "mve_filter": "exclude"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return kalshi_candidates(response.json())
