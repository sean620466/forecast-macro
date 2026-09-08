from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum
from itertools import pairwise
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
    """Legacy D-010 mid-price normalization; superseded by normalize_bucket_quotes (D-015).

    Kept for the review-3 tests and as the reference behaviour that D-015 replaced. Not used
    by the pricing pipeline.
    """
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


@dataclass(frozen=True)
class BucketProbabilities:
    """D-015 normalization of mutually exclusive YES quotes."""

    probabilities: dict[str, float]
    lower_bounds: dict[str, float]  # best bid per outcome
    upper_bounds: dict[str, float]  # best ask per outcome
    bid_sum: float
    ask_sum: float
    mid_sum: float


def normalize_bucket_quotes(
    quotes: dict[str, tuple[float, float]],
    *,
    expected_outcomes: tuple[str, ...] | None = None,
    completeness_tolerance: float = 0.01,
    max_width: float = 0.35,
) -> BucketProbabilities:
    """Turn (bid, ask) pairs for a complete outcome set into probabilities with bounds.

    The market is complete when the bid sum does not exceed 1 and the ask sum is at least 1
    (within tolerance). The point estimate removes the mid overround from each outcome in
    proportion to its spread, so wide tail quotes absorb the excess; that keeps every
    estimate inside its own [bid, ask] and makes the estimates sum to exactly 1 (D-015).
    """
    if len(quotes) < 2:
        raise ValueError("at least two outcome quotes are required")
    if expected_outcomes is not None and set(quotes) != set(expected_outcomes):
        raise ValueError("quote outcomes do not match the complete contract")
    if completeness_tolerance < 0 or max_width <= 0:
        raise ValueError("tolerance and width must be positive")
    for outcome, (bid, ask) in quotes.items():
        if not (math.isfinite(bid) and math.isfinite(ask)) or not 0 <= bid <= ask <= 1:
            raise ValueError(f"quote for {outcome} must satisfy 0 <= bid <= ask <= 1")
    bid_sum = sum(bid for bid, _ in quotes.values())
    ask_sum = sum(ask for _, ask in quotes.values())
    if bid_sum > 1.0 + completeness_tolerance:
        raise ValueError("bid sum exceeds 1: outcomes overlap or are not exclusive")
    if ask_sum < 1.0 - completeness_tolerance:
        raise ValueError("ask sum is below 1: outcome set is incomplete")
    if ask_sum - bid_sum > max_width:
        raise ValueError("quoted range is too wide to price the event")

    mids = {outcome: (bid + ask) / 2.0 for outcome, (bid, ask) in quotes.items()}
    spreads = {outcome: ask - bid for outcome, (bid, ask) in quotes.items()}
    mid_sum = sum(mids.values())
    excess = mid_sum - 1.0
    spread_total = sum(spreads.values())
    if spread_total > 0:
        estimates = {
            outcome: mids[outcome] - excess * spreads[outcome] / spread_total for outcome in quotes
        }
    else:
        # Zero spreads everywhere: the mids already sum to 1 within tolerance; scale.
        estimates = {outcome: mids[outcome] / mid_sum for outcome in quotes}
    for outcome, (bid, ask) in quotes.items():
        estimates[outcome] = min(max(estimates[outcome], bid), ask)
    return BucketProbabilities(
        probabilities=estimates,
        lower_bounds={outcome: bid for outcome, (bid, _) in quotes.items()},
        upper_bounds={outcome: ask for outcome, (_, ask) in quotes.items()},
        bid_sum=bid_sum,
        ask_sum=ask_sum,
        mid_sum=mid_sum,
    )


def normalize_threshold_ladder(
    ladder: dict[float, tuple[float, float]],
    *,
    step: float = 0.25,
    monotonic_tolerance: float = 0.02,
    max_width: float = 0.35,
) -> BucketProbabilities:
    """Turn a cumulative "greater than F" ladder into exclusive buckets with bounds.

    Kalshi rate markets quote YES = P(upper bound > F) for a grid of floors F. With floors
    F1 < F2 < ... < Fn on a fixed step, the exclusive outcomes are "<= F1", "== F1+step",
    ..., "== Fn", "> Fn" and their probabilities telescope: P(<= F1) = 1 - Y1,
    P(== Fk+step) = Yk - Yk+1, P(> Fn) = Yn. Bounds come from the bid/ask of the two rungs
    that form each difference. Mid-based estimates sum to exactly 1 by construction.
    """
    if len(ladder) < 2:
        raise ValueError("a threshold ladder needs at least two rungs")
    if step <= 0 or monotonic_tolerance < 0 or max_width <= 0:
        raise ValueError("step, tolerance and width must be positive")
    floors = sorted(ladder)
    for lower, upper in pairwise(floors):
        if abs((upper - lower) - step) > 1e-9:
            raise ValueError("ladder rungs must be contiguous on the fixed step")
    for floor, (bid, ask) in ladder.items():
        if not (math.isfinite(bid) and math.isfinite(ask)) or not 0 <= bid <= ask <= 1:
            raise ValueError(f"quote for rung {floor} must satisfy 0 <= bid <= ask <= 1")
    mids = {floor: (ladder[floor][0] + ladder[floor][1]) / 2.0 for floor in floors}
    # Monotonicity is judged on bounds, not mids: P(> F_high) cannot exceed P(> F_low), so a
    # higher rung's bid above a lower rung's ask is a real inconsistency. Mid inversions inside
    # overlapping bid-ask ranges are only spread noise (wide tails on far-dated ladders).
    for lower, upper in pairwise(floors):
        if ladder[upper][0] > ladder[lower][1] + monotonic_tolerance:
            raise ValueError("ladder is not monotone: a higher threshold trades above a lower one")

    def label(floor: float) -> str:
        return f"{floor:.2f}"

    probabilities: dict[str, float] = {}
    lower_bounds: dict[str, float] = {}
    upper_bounds: dict[str, float] = {}
    first, last = floors[0], floors[-1]
    bid1, ask1 = ladder[first]
    probabilities[f"le_{label(first)}"] = 1.0 - mids[first]
    lower_bounds[f"le_{label(first)}"] = 1.0 - ask1
    upper_bounds[f"le_{label(first)}"] = 1.0 - bid1
    for lower, upper in pairwise(floors):
        key = label(upper)  # outcome "upper bound == F_lower + step == upper"
        bid_lo, ask_lo = ladder[lower]
        bid_hi, ask_hi = ladder[upper]
        probabilities[key] = max(0.0, mids[lower] - mids[upper])
        lower_bounds[key] = max(0.0, bid_lo - ask_hi)
        upper_bounds[key] = min(1.0, max(0.0, ask_lo - bid_hi))
    bidn, askn = ladder[last]
    probabilities[f"gt_{label(last)}"] = mids[last]
    lower_bounds[f"gt_{label(last)}"] = bidn
    upper_bounds[f"gt_{label(last)}"] = askn

    total = sum(probabilities.values())
    if abs(total - 1.0) > 1e-9:  # only possible after max(0, ...) clipping of a violation
        probabilities = {key: value / total for key, value in probabilities.items()}
    bid_sum = sum(lower_bounds.values())
    ask_sum = sum(upper_bounds.values())
    if ask_sum - bid_sum > max_width:
        raise ValueError("ladder quotes are too wide to price the event")
    return BucketProbabilities(
        probabilities=probabilities,
        lower_bounds=lower_bounds,
        upper_bounds=upper_bounds,
        bid_sum=bid_sum,
        ask_sum=ask_sum,
        mid_sum=total,
    )
