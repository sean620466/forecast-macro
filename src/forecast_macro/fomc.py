from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class RateDecision(StrEnum):
    CUT = "cut"
    HOLD = "hold"
    HIKE = "hike"


@dataclass(frozen=True)
class FomcMeeting:
    decision_at: datetime
    upper_before: float
    upper_after: float

    @property
    def change_bps(self) -> int:
        return round((self.upper_after - self.upper_before) * 100)

    @property
    def decision(self) -> RateDecision:
        if self.change_bps < 0:
            return RateDecision.CUT
        if self.change_bps > 0:
            return RateDecision.HIKE
        return RateDecision.HOLD


def label_rate_decision(*, upper_before: float, upper_after: float) -> RateDecision:
    change = round((upper_after - upper_before) * 100)
    if change < 0:
        return RateDecision.CUT
    if change > 0:
        return RateDecision.HIKE
    return RateDecision.HOLD


def to_binary_model_outcome(decision: RateDecision) -> str:
    return "cut" if decision is RateDecision.CUT else "hold_or_hike"
