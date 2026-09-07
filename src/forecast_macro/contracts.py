from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


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
    observed_at: datetime
    outcomes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.observed_at >= self.meeting_at:
            raise ValueError("market observation must precede the meeting")
        if len(self.outcomes) < 2 or len(set(self.outcomes)) != len(self.outcomes):
            raise ValueError("contract requires at least two unique outcomes")


def normalize_outcome_prices(prices: dict[str, float], *, tolerance: float = 0.15) -> dict[str, float]:
    """Remove simple overround by normalizing mutually exclusive outcome prices."""
    if len(prices) < 2:
        raise ValueError("at least two outcome prices are required")
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")
    if not all(math.isfinite(value) and 0 < value <= 1 for value in prices.values()):
        raise ValueError("prices must be finite and in (0, 1]")
    total = sum(prices.values())
    if abs(total - 1.0) > tolerance:
        raise ValueError("outcome prices are too far from a complete market")
    return {outcome: price / total for outcome, price in prices.items()}
