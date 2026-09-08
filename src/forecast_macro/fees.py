from __future__ import annotations

import math
from dataclasses import dataclass

# Venue fee schedules (task 19). Every entry names its source and whether the constants were
# read from an official document. Fees are per share/contract in the venue's currency and are
# expressed here in probability units (a $1 payout contract), so they subtract directly from
# an edge measured in probability points (D-003).


@dataclass(frozen=True)
class FeeSchedule:
    fee_schedule_id: str
    venue: str
    description: str
    taker_rate: float  # fee = taker_rate * p * (1 - p) per share
    maker_rate: float
    round_up_increment: float  # 0 = no rounding; Kalshi rounds up to a centicent (0.0001)
    source_url: str
    fetched_at: str
    verified: bool  # constants read from the venue's published schedule

    def taker_fee(self, price: float) -> float:
        if not 0.0 <= price <= 1.0:
            raise ValueError("price must be between 0 and 1")
        fee = self.taker_rate * price * (1.0 - price)
        if self.round_up_increment > 0:
            steps = math.ceil(fee / self.round_up_increment - 1e-9)
            fee = steps * self.round_up_increment
        return fee

    def break_even_probability(self, ask: float) -> float:
        """Model probability needed for a YES purchase at `ask` to have zero expected value."""
        return min(1.0, ask + self.taker_fee(ask))

    def net_edge(self, model_probability: float, ask: float) -> float:
        """Edge after the taker fee on a YES purchase; negative means the trade loses money."""
        if not 0.0 <= model_probability <= 1.0:
            raise ValueError("model probability must be between 0 and 1")
        return model_probability - self.break_even_probability(ask)


FEE_SCHEDULES: dict[str, FeeSchedule] = {
    "polymarket-economics": FeeSchedule(
        fee_schedule_id="polymarket-economics",
        venue="polymarket",
        description="Polymarket taker fee, Economics category (makers pay nothing)",
        taker_rate=0.05,
        maker_rate=0.0,
        round_up_increment=0.0,
        source_url="https://docs.polymarket.com/polymarket-learn/trading/fees",
        fetched_at="2026-09-08T03:40:00+00:00",
        verified=True,
    ),
    "kalshi-quadratic_with_maker_fees-x1": FeeSchedule(
        fee_schedule_id="kalshi-quadratic_with_maker_fees-x1",
        venue="kalshi",
        description=(
            "Kalshi general trading fee: round up(M x 0.07 x C x P x (1-P)), maker fee "
            "round up(M x 0.0175 x C x P x (1-P)); M from the series API (KXFED: 1). "
            "Rounded up to a centicent. Fee schedule last updated July 7, 2026."
        ),
        taker_rate=0.07,
        maker_rate=0.0175,
        round_up_increment=0.0001,
        source_url="https://kalshi.com/docs/kalshi-fee-schedule.pdf",
        fetched_at="2026-09-08T08:51:00+00:00",
        verified=True,
    ),
}


def kalshi_fee_schedule_id(fee_type: str, fee_multiplier: float) -> str:
    multiplier = int(fee_multiplier) if float(fee_multiplier).is_integer() else fee_multiplier
    return f"kalshi-{fee_type}-x{multiplier}"


def schedule_for(fee_schedule_id: str) -> FeeSchedule | None:
    return FEE_SCHEDULES.get(fee_schedule_id)


def fee_summary(fee_schedule_id: str, ask: float) -> dict[str, object]:
    """Per-contract fee facts for a record; unknown schedules are reported, not guessed."""
    schedule = schedule_for(fee_schedule_id)
    if schedule is None:
        return {"fee_schedule_id": fee_schedule_id, "known": False}
    return {
        "fee_schedule_id": fee_schedule_id,
        "known": True,
        "verified": schedule.verified,
        "taker_fee_at_ask": schedule.taker_fee(ask),
        "break_even_probability": schedule.break_even_probability(ask),
        "source_url": schedule.source_url,
    }
