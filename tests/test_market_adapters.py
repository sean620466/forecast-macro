from datetime import UTC, datetime

import pytest

from forecast_macro.data.kalshi import parse_kalshi_orderbook
from forecast_macro.data.polymarket import (
    parse_polymarket_orderbook,
    parse_polymarket_orderbooks,
)

NOW = datetime(2026, 9, 7, 18, 0, tzinfo=UTC)


def test_kalshi_derives_yes_ask_from_no_bid() -> None:
    quote = parse_kalshi_orderbook(
        {"orderbook_fp": {"yes_dollars": [["0.42", 30]], "no_dollars": [["0.55", 20]]}},
        ticker="KXFED-TEST",
        observed_at=NOW,
    )

    assert quote.bid == 0.42
    assert quote.ask == pytest.approx(0.45)
    assert quote.mid == pytest.approx(0.435)
    assert quote.venue == "kalshi"


def test_polymarket_uses_best_bid_and_ask() -> None:
    quote = parse_polymarket_orderbook(
        {
            "market": "condition-id",
            "tick_size": "0.001",
            "bids": [{"price": "0.39", "size": "10"}, {"price": "0.41", "size": "8"}],
            "asks": [{"price": "0.46", "size": "7"}, {"price": "0.44", "size": "9"}],
        },
        token_id="yes-token",
        observed_at=NOW,
    )

    assert quote.bid == 0.41
    assert quote.ask == 0.44
    assert quote.mid == pytest.approx(0.425)


def test_adapters_reject_one_sided_books() -> None:
    with pytest.raises(ValueError, match="both YES and NO"):
        parse_kalshi_orderbook(
            {"orderbook": {"yes_dollars": [["0.4", 1]], "no_dollars": []}},
            ticker="KXFED-TEST",
            observed_at=NOW,
        )


def test_polymarket_batch_books_use_exchange_timestamps() -> None:
    quotes = parse_polymarket_orderbooks(
        [
            {
                "market": "condition-id",
                "asset_id": "yes-token",
                "timestamp": "1788825600000",
                "tick_size": "0.01",
                "bids": [{"price": "0.40", "size": "8"}],
                "asks": [{"price": "0.42", "size": "9"}],
            }
        ]
    )
    assert quotes["yes-token"].observed_at == datetime(2026, 9, 8, tzinfo=UTC)
