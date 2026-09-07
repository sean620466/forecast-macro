from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum
from typing import Literal
from zoneinfo import ZoneInfo


class FedOutcome(StrEnum):
    HIKE = "hike"
    HOLD = "hold"
    CUT_25 = "cut_25"
    CUT_50_PLUS = "cut_50_plus"


def bucket_rate_change(change_bps: int) -> FedOutcome:
    if change_bps > 0:
        return FedOutcome.HIKE
    if change_bps == 0:
        return FedOutcome.HOLD
    if change_bps > -50:
        return FedOutcome.CUT_25
    return FedOutcome.CUT_50_PLUS


@dataclass(frozen=True)
class PredictionContract:
    contract_id: str
    meeting_at: datetime
    closes_at: datetime
    observed_at: datetime
    outcomes: tuple[str, ...]
    venue: str = "unknown"
    venue_contract_id: str | None = None
    rules_text_hash: str | None = None

    def __post_init__(self) -> None:
        timestamps = (self.meeting_at, self.closes_at, self.observed_at)
        if any(value.tzinfo is None for value in timestamps):
            raise ValueError("contract timestamps must be timezone-aware")
        if self.closes_at > self.meeting_at:
            raise ValueError("contract close must not follow the meeting")
        if self.observed_at >= self.closes_at:
            raise ValueError("market observation must precede contract close")
        if len(self.outcomes) < 2 or len(set(self.outcomes)) != len(self.outcomes):
            raise ValueError("contract requires at least two unique outcomes")


@dataclass(frozen=True)
class OutcomeQuote:
    outcome_id: str
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    observed_at: datetime
    tick_size: float
    fee_schedule_id: str
    venue: str = "unknown"
    venue_contract_id: str | None = None
    quote_type: Literal["book"] = "book"

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("quote timestamp must be timezone-aware")
        if not 0 <= self.bid <= self.ask <= 1:
            raise ValueError("quote requires 0 <= bid <= ask <= 1")
        if self.bid_size < 0 or self.ask_size < 0 or self.tick_size <= 0:
            raise ValueError("sizes must be non-negative and tick_size positive")

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0


def fomc_decision_time(meeting_date: date) -> datetime:
    return datetime.combine(meeting_date, time(14, 0), tzinfo=ZoneInfo("America/New_York"))


def normalize_outcome_prices(
    prices: dict[str, float],
    *,
    expected_outcomes: tuple[str, ...] | None = None,
    quote_type: Literal["mid"] = "mid",
    tolerance: float = 0.05,
) -> dict[str, float]:
    """Remove simple overround by normalizing mutually exclusive outcome prices."""
    if len(prices) < 2:
        raise ValueError("at least two outcome prices are required")
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")
    if quote_type != "mid":
        raise ValueError("only same-timestamp mid prices may be normalized")
    if expected_outcomes is not None and set(prices) != set(expected_outcomes):
        raise ValueError("price outcomes do not match the complete contract")
    if not all(math.isfinite(value) and 0 < value <= 1 for value in prices.values()):
        raise ValueError("prices must be finite and in (0, 1]")
    total = sum(prices.values())
    if abs(total - 1.0) > tolerance:
        raise ValueError("outcome prices are too far from a complete market")
    return {outcome: price / total for outcome, price in prices.items()}
