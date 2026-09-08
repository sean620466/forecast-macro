from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from forecast_macro.contracts import OutcomeQuote
from forecast_macro.market_discovery import MarketCandidate, kalshi_candidates

KALSHI_API_URL = "https://external-api.kalshi.com/trade-api/v2"
# Identify the research client explicitly; anonymous default agents are more often rate-limited.
REQUEST_HEADERS = {"User-Agent": "forecast-macro/0.1 (+https://github.com/sean620466/forecast-macro)"}


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
        fee_schedule_id="kalshi-quadratic_with_maker_fees-x1",
        venue="kalshi",
        venue_contract_id=ticker,
    )


class KalshiPublicClient:
    def __init__(self, *, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def orderbook(self, ticker: str) -> OutcomeQuote:
        response = httpx.get(
            f"{KALSHI_API_URL}/markets/{ticker}/orderbook",
            headers=REQUEST_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return parse_kalshi_orderbook(
            response.json(), ticker=ticker, observed_at=datetime.now(UTC)
        )

    def market(self, ticker: str) -> dict[str, Any]:
        response = httpx.get(
            f"{KALSHI_API_URL}/markets/{ticker}", headers=REQUEST_HEADERS, timeout=self.timeout
        )
        response.raise_for_status()
        payload = response.json()
        return dict(payload.get("market") or payload)

    def discover_open_macro_markets(self) -> list[MarketCandidate]:
        candidates: list[MarketCandidate] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
        while True:
            params = {"status": "open", "limit": 1000, "mve_filter": "exclude"}
            if cursor:
                params["cursor"] = cursor
            response = httpx.get(
                f"{KALSHI_API_URL}/markets",
                params=params,
                headers=REQUEST_HEADERS,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            candidates.extend(kalshi_candidates(payload))
            next_cursor = str(payload.get("cursor") or "")
            if not next_cursor:
                break
            if next_cursor in seen_cursors:
                raise ValueError("Kalshi pagination returned a repeated cursor")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        return candidates


def parse_kalshi_market_quote(
    market: dict[str, Any],
    *,
    observed_at: datetime,
    fee_schedule_id: str = "kalshi-quadratic_with_maker_fees-x1",
) -> OutcomeQuote:
    """Top-of-book YES quote from a /markets row (dollar fields preferred, cents fallback)."""

    def price(dollar_key: str, cent_key: str) -> float:
        if market.get(dollar_key) is not None:
            return float(market[dollar_key])
        return float(market.get(cent_key) or 0) / 100.0

    return OutcomeQuote(
        outcome_id="yes",
        bid=price("yes_bid_dollars", "yes_bid"),
        ask=price("yes_ask_dollars", "yes_ask"),
        bid_size=float(market.get("yes_bid_size_fp") or 0),
        ask_size=float(market.get("yes_ask_size_fp") or 0),
        observed_at=observed_at,
        tick_size=0.01,
        fee_schedule_id=fee_schedule_id,
        venue="kalshi",
        venue_contract_id=str(market.get("ticker") or "") or None,
    )


class KalshiEventClient(KalshiPublicClient):
    def event_markets(self, event_ticker: str) -> tuple[list[dict[str, Any]], datetime]:
        """All markets of one event with their top-of-book quotes, plus the fetch time."""
        response = httpx.get(
            f"{KALSHI_API_URL}/markets",
            params={"event_ticker": event_ticker, "limit": 200},
            headers=REQUEST_HEADERS,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return list(response.json().get("markets", [])), datetime.now(UTC)
