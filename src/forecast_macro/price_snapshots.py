from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from itertools import pairwise
from typing import Any

from forecast_macro.contracts import OutcomeQuote, normalize_threshold_ladder
from forecast_macro.fees import fee_summary, schedule_for
from forecast_macro.market_discovery import MacroTopic, MarketCandidate
from forecast_macro.market_pricing import build_event_price_snapshot
from forecast_macro.market_review import (
    CandidateReview,
    ReviewStatus,
    is_threshold_ladder,
    ladder_step_for,
)


@dataclass(frozen=True)
class EventPriceRecord:
    """One attempt to price an approved event. probabilities is empty when the gate refused."""

    venue: str
    venue_event_id: str
    topic: str
    observed_at: str
    outcome_at: str | None
    contracts: dict[str, str]  # venue_market_id -> title
    probabilities: dict[str, float]
    probability_bounds: dict[str, list[float]]  # venue_market_id -> [bid, ask] (D-015)
    completeness: dict[str, float]  # bid_sum, ask_sum, mid_sum
    source_mid_prices: dict[str, float]
    quotes: dict[str, dict[str, object]]
    rules_text_hashes: dict[str, str]
    book_updated_at: dict[str, str]
    rejected_reason: str | None
    # D-012: prices are recorded for a future market baseline; nothing here is a signal.
    signal_eligible: bool = False
    # Two-leg taker fees per derived bucket (ladders only), in probability units (R19-M2).
    bucket_fees: dict[str, float] | None = None
    # Statistic the contracts settle on, as identified from the verified rules (task 40); lets
    # the comparison scripts tell core from headline CPI ladders on the same topic.
    contract_series: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def candidate_from_row(row: Mapping[str, Any]) -> MarketCandidate:
    closes_at = row.get("closes_at")
    return MarketCandidate(
        venue=str(row["venue"]),
        venue_market_id=str(row["venue_market_id"]),
        venue_event_id=str(row["venue_event_id"]) if row.get("venue_event_id") else None,
        title=str(row.get("title", "")),
        topic=MacroTopic(str(row["topic"])),
        closes_at=datetime.fromisoformat(str(closes_at)) if closes_at else None,
        outcome_labels=tuple(str(v) for v in row.get("outcome_labels", ())),
        outcome_token_ids=tuple(str(v) for v in row.get("outcome_token_ids", ())),
        match_basis=str(row.get("match_basis", "")),
        requires_review=bool(row.get("requires_review", True)),
        close_time_verified=bool(row.get("close_time_verified", False)),
        venue_close_raw=row.get("venue_close_raw"),
        strike=float(row["strike"]) if row.get("strike") is not None else None,
        strike_type=row.get("strike_type"),
    )


def review_from_row(row: Mapping[str, Any]) -> CandidateReview:
    return CandidateReview(
        venue=str(row["venue"]),
        venue_event_id=str(row["venue_event_id"]) if row.get("venue_event_id") else None,
        venue_market_id=str(row["venue_market_id"]),
        topic=str(row["topic"]),
        status=ReviewStatus(str(row["status"])),
        checks_passed=tuple(row.get("checks_passed", ())),
        blockers=tuple(row.get("blockers", ())),
    )


def approved_events(
    candidates: Sequence[Mapping[str, Any]], reviews: Sequence[Mapping[str, Any]]
) -> dict[tuple[str, str], list[MarketCandidate]]:
    """Events whose every discovered contract is approved. A partial event is never priced."""
    status_by_market = {
        (str(r["venue"]), str(r["venue_market_id"])): str(r["status"]) for r in reviews
    }
    grouped: dict[tuple[str, str], list[MarketCandidate]] = defaultdict(list)
    for row in candidates:
        if not row.get("venue_event_id"):
            continue
        grouped[(str(row["venue"]), str(row["venue_event_id"]))].append(candidate_from_row(row))
    return {
        key: members
        for key, members in grouped.items()
        if len(members) >= 2
        and all(
            status_by_market.get((m.venue, m.venue_market_id)) == ReviewStatus.APPROVED.value
            for m in members
        )
    }


def price_event(
    members: Sequence[MarketCandidate],
    reviews: Mapping[str, CandidateReview],
    quotes: Mapping[str, OutcomeQuote],
    rules_text_hashes: Mapping[str, str],
    *,
    as_of: datetime,
    outcome_at: datetime | None,
    book_updated_at: Mapping[str, datetime] | None = None,
    contract_series: str | None = None,
) -> EventPriceRecord:
    venue = members[0].venue
    event_id = members[0].venue_event_id or ""
    yes_tokens = {m.venue_market_id: m.outcome_token_ids[0] for m in members if m.outcome_token_ids}
    quote_rows: dict[str, dict[str, object]] = {}
    for market_id, token in yes_tokens.items():
        quote = quotes.get(token)
        if quote is None:
            continue
        quote_rows[market_id] = {
            "token_id": token,
            "bid": quote.bid,
            "ask": quote.ask,
            "mid": quote.mid,
            "bid_size": quote.bid_size,
            "ask_size": quote.ask_size,
            "tick_size": quote.tick_size,
            "fees": fee_summary(quote.fee_schedule_id, quote.ask),
        }
    updated = {
        market_id: (book_updated_at or {}).get(token).isoformat()  # type: ignore[union-attr]
        for market_id, token in yes_tokens.items()
        if (book_updated_at or {}).get(token) is not None
    }
    base = {
        "venue": venue,
        "venue_event_id": event_id,
        "topic": members[0].topic.value,
        "observed_at": as_of.isoformat(),
        "outcome_at": outcome_at.isoformat() if outcome_at else None,
        "contracts": {m.venue_market_id: m.title for m in members},
        "quotes": quote_rows,
        "rules_text_hashes": {
            m.venue_market_id: rules_text_hashes.get(m.venue_market_id, "") for m in members
        },
        "book_updated_at": updated,
        "contract_series": contract_series,
    }
    try:
        snapshot = build_event_price_snapshot(
            members, reviews, quotes, rules_text_hashes, as_of=as_of
        )
    except ValueError as error:
        return EventPriceRecord(
            **base,
            probabilities={},
            probability_bounds={},
            completeness={},
            source_mid_prices={},
            rejected_reason=str(error),
        )
    return EventPriceRecord(
        **base,
        probabilities=snapshot.probabilities,
        probability_bounds={
            market_id: [snapshot.lower_bounds[market_id], snapshot.upper_bounds[market_id]]
            for market_id in snapshot.probabilities
        },
        completeness={
            "bid_sum": snapshot.bid_sum,
            "ask_sum": snapshot.ask_sum,
            "mid_sum": snapshot.mid_sum,
        },
        source_mid_prices=snapshot.source_mid_prices,
        rejected_reason=None,
    )


def _months_ahead(as_of: datetime, outcome_at: datetime) -> int:
    months = (outcome_at.year - as_of.year) * 12 + (outcome_at.month - as_of.month)
    if outcome_at.day < as_of.day:
        months -= 1
    return months


def ladder_width_limit(as_of: datetime, outcome_at: datetime | None) -> float:
    """D-018: 0.35 up to two months out, +0.05 per further month, capped at 0.60.

    Recorded for information since D-019; the gate itself is `ladder_spread_limits`.
    """
    if outcome_at is None:
        return 0.35
    return min(0.60, 0.35 + 0.05 * max(0, _months_ahead(as_of, outcome_at) - 2))


# D-019 base limits: the mean rung spread that flags low liquidity, and the widest single rung.
MEAN_RUNG_SPREAD_LIMIT = 0.05
MAX_RUNG_SPREAD_LIMIT = 0.12


def ladder_spread_limits(as_of: datetime, outcome_at: datetime | None) -> tuple[float, float]:
    """D-019: (mean rung spread limit, max rung spread limit), relaxed +0.01 per month beyond two.

    Caps are 0.10 and 0.20. The gate is per rung because the exclusive-bucket width of a
    ladder is roughly twice the sum of rung spreads, so the D-015/D-018 width gate measured
    the rung count rather than the quotes (task 37).
    """
    extra = 0.0
    if outcome_at is not None:
        extra = 0.01 * max(0, _months_ahead(as_of, outcome_at) - 2)
    return min(0.10, MEAN_RUNG_SPREAD_LIMIT + extra), min(0.20, MAX_RUNG_SPREAD_LIMIT + extra)


def is_ladder_event(members: Sequence[MarketCandidate]) -> bool:
    return is_threshold_ladder([asdict(m) for m in members])


def price_ladder_event(
    members: Sequence[MarketCandidate],
    reviews: Mapping[str, CandidateReview],
    quotes: Mapping[str, OutcomeQuote],  # keyed by venue_market_id (ticker)
    rules_text_hashes: Mapping[str, str],
    *,
    as_of: datetime,
    outcome_at: datetime | None,
    wide_spread: float = 0.10,
    max_age_seconds: float = 120.0,
    contract_series: str | None = None,
) -> EventPriceRecord:
    """Price a cumulative threshold ladder (Kalshi "greater than F") as exclusive buckets.

    Liquidity is judged per rung (D-019): the mean and the widest bid-ask spread across the
    rungs must stay under `ladder_spread_limits`. Wide rungs are listed in the record; the
    exclusive-bucket width (sum of asks minus sum of bids) is recorded but no longer gates,
    because it grows with the number of rungs rather than with the quotes.
    """
    venue = members[0].venue
    event_id = members[0].venue_event_id or ""
    quote_rows: dict[str, dict[str, object]] = {}
    ladder: dict[float, tuple[float, float]] = {}
    problems: list[str] = []
    wide_rungs: list[str] = []
    fee_ids: set[str] = set()
    asks_by_floor: dict[float, float] = {}
    for member in sorted(members, key=lambda m: m.strike or 0.0):
        review = reviews.get(member.venue_market_id)
        if review is None or review.status is not ReviewStatus.APPROVED:
            problems.append(f"{member.venue_market_id}: not approved")
        quote = quotes.get(member.venue_market_id)
        if quote is None:
            problems.append(f"{member.venue_market_id}: missing quote")
            continue
        quote_rows[member.venue_market_id] = {
            "strike": member.strike or 0.0,
            "bid": quote.bid,
            "ask": quote.ask,
            "mid": quote.mid,
            "bid_size": quote.bid_size,
            "ask_size": quote.ask_size,
            "fees": fee_summary(quote.fee_schedule_id, quote.ask),
        }
        if quote.ask - quote.bid > wide_spread:
            wide_rungs.append(member.venue_market_id)
        fee_ids.add(quote.fee_schedule_id)
        asks_by_floor[float(member.strike or 0.0)] = quote.ask
        if quote.observed_at > as_of or (as_of - quote.observed_at).total_seconds() > max_age_seconds:
            problems.append(f"{member.venue_market_id}: quote is stale or from the future")
        if not rules_text_hashes.get(member.venue_market_id):
            problems.append(f"{member.venue_market_id}: missing rules hash")
        ladder[float(member.strike or 0.0)] = (quote.bid, quote.ask)
    base = {
        "venue": venue,
        "venue_event_id": event_id,
        "topic": members[0].topic.value,
        "observed_at": as_of.isoformat(),
        "outcome_at": outcome_at.isoformat() if outcome_at else None,
        "contracts": {m.venue_market_id: m.title for m in members},
        "quotes": quote_rows,
        "rules_text_hashes": {
            m.venue_market_id: rules_text_hashes.get(m.venue_market_id, "") for m in members
        },
        "book_updated_at": {"wide_rungs": wide_rungs} if wide_rungs else {},
        "contract_series": contract_series,
    }
    if problems:
        return EventPriceRecord(
            **base,
            probabilities={},
            probability_bounds={},
            completeness={},
            source_mid_prices={},
            rejected_reason="; ".join(problems),
        )
    # D-019: per-rung liquidity gate, relaxed with horizon like D-018 was.
    spreads = [ask - bid for bid, ask in ladder.values()]
    mean_spread = sum(spreads) / len(spreads)
    max_spread = max(spreads)
    mean_limit, max_limit = ladder_spread_limits(as_of, outcome_at)
    width_limit = ladder_width_limit(as_of, outcome_at)
    if mean_spread > mean_limit + 1e-12 or max_spread > max_limit + 1e-12:
        return EventPriceRecord(
            **base,
            probabilities={},
            probability_bounds={},
            completeness={
                "mean_rung_spread": mean_spread,
                "max_rung_spread": max_spread,
                "mean_rung_limit": mean_limit,
                "max_rung_limit": max_limit,
            },
            source_mid_prices={},
            rejected_reason=(
                f"ladder rung spreads too wide (mean {mean_spread:.3f} > {mean_limit:.2f} or "
                f"max {max_spread:.3f} > {max_limit:.2f}, D-019)"
            ),
        )
    step = ladder_step_for(members[0].topic.value)
    try:
        normalized = normalize_threshold_ladder(ladder, step=step, max_width=None)
    except ValueError as error:
        return EventPriceRecord(
            **base,
            probabilities={},
            probability_bounds={},
            completeness={},
            source_mid_prices={},
            rejected_reason=str(error),
        )
    # Two-leg fees (R19-M2): an exclusive bucket between floors F_k and F_k+1 is built from
    # the two adjacent rung contracts, so both taker fees apply. Tail buckets use one rung.
    schedule = schedule_for(next(iter(fee_ids))) if len(fee_ids) == 1 else None
    floors = sorted(ladder)
    bucket_fees: dict[str, float] = {}
    if schedule is not None:
        first, last = floors[0], floors[-1]
        bucket_fees[f"le_{first:.2f}"] = schedule.taker_fee(asks_by_floor[first])
        for lower, upper in pairwise(floors):
            bucket_fees[f"{upper:.2f}"] = schedule.taker_fee(asks_by_floor[lower]) + schedule.taker_fee(
                asks_by_floor[upper]
            )
        bucket_fees[f"gt_{last:.2f}"] = schedule.taker_fee(asks_by_floor[last])
    width = normalized.ask_sum - normalized.bid_sum
    completeness: dict[str, float] = {
        "bid_sum": normalized.bid_sum,
        "ask_sum": normalized.ask_sum,
        "mid_sum": normalized.mid_sum,
        "wide_rung_count": float(len(wide_rungs)),
        "width": width,
        "width_limit": width_limit,
        "mean_rung_spread": mean_spread,
        "max_rung_spread": max_spread,
        "mean_rung_limit": mean_limit,
        "max_rung_limit": max_limit,
        # D-019: low liquidity means the mean rung spread exceeds the base limit.
        "low_liquidity": 1.0 if mean_spread > MEAN_RUNG_SPREAD_LIMIT + 1e-12 else 0.0,
    }
    return EventPriceRecord(
        **base,
        probabilities=normalized.probabilities,
        probability_bounds={
            key: [normalized.lower_bounds[key], normalized.upper_bounds[key]]
            for key in normalized.probabilities
        },
        completeness=completeness,
        source_mid_prices={f"{floor:.2f}": (b + a) / 2 for floor, (b, a) in ladder.items()},
        rejected_reason=None,
        bucket_fees=bucket_fees,
    )
