"""Task 40 (D-019): ladder liquidity judged per rung; Kalshi BLS ladders enter the comparisons."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from forecast_macro.alerts import new_scored_records
from forecast_macro.contracts import OutcomeQuote, normalize_threshold_ladder
from forecast_macro.market_review import CandidateReview, ReviewStatus
from forecast_macro.models.unemployment import next_month_bucket_probabilities, validate_buckets
from forecast_macro.price_snapshots import (
    EventPriceRecord,
    candidate_from_row,
    ladder_spread_limits,
    price_ladder_event,
)
from forecast_macro.unemployment_comparison import (
    buckets_from_record,
    is_ladder_keys,
    ladder_bucket_titles,
    ladder_buckets,
)
from forecast_macro.unemployment_scoring import (
    final_record_per_release,
    score_unemployment_comparisons,
)

NOW = datetime(2026, 9, 8, 17, 0, tzinfo=UTC)


def test_spread_limits_relax_with_horizon_and_cap() -> None:
    assert ladder_spread_limits(NOW, None) == (0.05, 0.12)
    assert ladder_spread_limits(NOW, datetime(2026, 10, 2, tzinfo=UTC)) == (0.05, 0.12)
    mean, high = ladder_spread_limits(NOW, datetime(2026, 12, 4, tzinfo=UTC))  # 2 months + 26 days
    assert (mean, high) == pytest.approx((0.05, 0.12))
    mean, high = ladder_spread_limits(NOW, datetime(2027, 1, 27, tzinfo=UTC))  # 4 months
    assert (mean, high) == pytest.approx((0.07, 0.14))
    assert ladder_spread_limits(NOW, datetime(2030, 1, 1, tzinfo=UTC)) == (0.10, 0.20)


def _ladder_members(event: str, floors, topic: str):
    rows = []
    for floor in floors:
        rows.append(
            {
                "venue": "kalshi",
                "venue_market_id": f"{event}-T{floor:.1f}",
                "venue_event_id": event,
                "title": f"Will the unemployment rate be above {floor:.1f}% in September 2026?",
                "topic": topic,
                "outcome_labels": ["Yes", "No"],
                "outcome_token_ids": ["yes", "no"],
                "strike": floor,
                "strike_type": "greater",
            }
        )
    return [candidate_from_row(r) for r in rows]


def _quote(ticker: str, bid: float, ask: float) -> OutcomeQuote:
    return OutcomeQuote(
        outcome_id=ticker,
        bid=round(bid, 4),
        ask=round(ask, 4),
        bid_size=100.0,
        ask_size=100.0,
        observed_at=NOW,
        tick_size=0.01,
        fee_schedule_id="kalshi-quadratic_with_maker_fees-x1",
        venue="kalshi",
        venue_contract_id=ticker,
    )


def _price(floors, spreads, topic="unemployment", outcome_at=datetime(2026, 10, 2, 12, 30, tzinfo=UTC)):
    event = "KXU3-26SEP"
    members = _ladder_members(event, floors, topic)
    reviews = {
        m.venue_market_id: CandidateReview("kalshi", event, m.venue_market_id, topic, ReviewStatus.APPROVED, (), ())
        for m in members
    }
    # Cumulative YES probabilities decreasing in the floor; each rung quoted mid ± spread/2.
    n = len(floors)
    quotes = {}
    for i, (m, spread) in enumerate(zip(members, spreads, strict=True)):
        mid = 0.95 - 0.9 * i / (n - 1)
        quotes[m.venue_market_id] = _quote(m.venue_market_id, max(0.0, mid - spread / 2), min(1.0, mid + spread / 2))
    return price_ladder_event(
        members,
        reviews,
        quotes,
        {m.venue_market_id: "sha256:x" for m in members},
        as_of=NOW,
        outcome_at=outcome_at,
        contract_series="unemployment_rate_sa",
    )


FLOORS = [round(3.8 + 0.1 * i, 1) for i in range(14)]  # 3.8 .. 5.1


def test_fourteen_rung_ladder_with_tight_rungs_is_priced_even_though_its_width_exceeds_035() -> None:
    record = _price(FLOORS, [0.04] * 14)
    assert record.rejected_reason is None
    assert record.contract_series == "unemployment_rate_sa"
    c = record.completeness
    assert c["mean_rung_spread"] == pytest.approx(0.04)
    assert c["max_rung_spread"] == pytest.approx(0.04)
    assert c["width"] > 0.35  # exactly what D-015/D-018 refused: ~2 × Σ spreads
    assert c["low_liquidity"] == 0.0
    assert sum(record.probabilities.values()) == pytest.approx(1.0)
    keys = list(record.probabilities)
    assert keys[0] == "le_3.80" and keys[-1] == "gt_5.10" and "4.10" in keys


def test_wide_mean_or_single_wide_rung_is_refused_with_the_reason_recorded() -> None:
    record = _price(FLOORS, [0.06] * 14)
    assert record.probabilities == {} and "mean 0.060 > 0.05" in (record.rejected_reason or "")
    assert record.completeness["mean_rung_spread"] == pytest.approx(0.06)
    spreads = [0.02] * 14
    spreads[6] = 0.15  # one wide rung in the active middle of the ladder
    record = _price(FLOORS, spreads)
    assert record.probabilities == {} and "max 0.150 > 0.12" in (record.rejected_reason or "")


def test_far_dated_ladder_uses_relaxed_limits_and_is_flagged_low_liquidity() -> None:
    record = _price(FLOORS, [0.055] * 14, outcome_at=datetime(2026, 12, 4, 12, 30, tzinfo=UTC))
    assert record.rejected_reason is not None  # 2 months + days: no relaxation yet
    record = _price(FLOORS, [0.055] * 14, outcome_at=datetime(2027, 1, 8, 12, 30, tzinfo=UTC))
    assert record.rejected_reason is None
    assert record.completeness["mean_rung_limit"] == pytest.approx(0.07)
    assert record.completeness["low_liquidity"] == 1.0


def test_width_gate_can_be_switched_off_in_the_normalizer() -> None:
    ladder = {f: (0.5 - 0.03, 0.5 + 0.03) for f in [3.8, 3.9, 4.0, 4.1]}
    with pytest.raises(ValueError, match="too wide"):
        normalize_threshold_ladder(ladder, step=0.1, max_width=0.1)
    normalize_threshold_ladder(ladder, step=0.1, max_width=None)


def test_ladder_keys_become_contiguous_tenth_point_buckets() -> None:
    keys = ["le_3.80", "3.90", "4.00", "4.10", "gt_4.10"]
    assert is_ladder_keys(keys)
    buckets = ladder_buckets(keys, step=0.1)
    validate_buckets(buckets)
    assert [(b.kind, b.value) for b in buckets] == [
        ("lower", 3.8), ("exact", 3.9), ("exact", 4.0), ("exact", 4.1), ("upper", 4.2)
    ]
    # "above 4.1" pays for a published 4.2, so 4.2 belongs to the upper tail.
    by_key = {b.key: b for b in buckets}
    assert by_key["gt_4.10"].contains(4.2) and not by_key["4.10"].contains(4.2)
    assert by_key["le_3.80"].contains(3.5)
    titles = ladder_bucket_titles(keys, step=0.1, subject="KXU3-26SEP ladder bucket")
    assert titles["le_3.80"].endswith("will be ≤3.8%") and titles["gt_4.10"].endswith("will be ≥4.2%")
    probabilities = next_month_bucket_probabilities(4.0, {-0.1: 0.3, 0.0: 0.5, 0.2: 0.2}, buckets)
    assert {p.outcome: p.probability for p in probabilities} == pytest.approx(
        {"le_3.80": 0.0, "3.90": 0.3, "4.00": 0.5, "4.10": 0.0, "gt_4.10": 0.2}
    )


def test_buckets_from_record_reads_ladder_keys_from_probabilities_or_comparison_titles() -> None:
    record = {"topic": "cpi", "probabilities": {"le_2.10": 0.1, "2.20": 0.6, "gt_2.20": 0.3}}
    assert [b.kind for b in buckets_from_record(record)] == ["lower", "exact", "upper"]
    titles = ladder_bucket_titles(list(record["probabilities"]), step=0.1, subject="x")
    again = buckets_from_record({"topic": "cpi", "contracts": titles})
    assert [(b.key, b.value) for b in again] == [("le_2.10", 2.1), ("2.20", 2.2), ("gt_2.20", 2.3)]


def _comparison(as_of: str, venue: str, model, market, titles):
    return {
        "as_of": as_of,
        "release_at": "2026-10-02T08:30:00-04:00",
        "reference_period": "2026-09",
        "venue": venue,
        "topic": "unemployment",
        "bucket_titles": titles,
        "model": model,
        "market": market,
    }


def test_each_venue_is_scored_separately_and_alerted_separately() -> None:
    poly_titles = {"low": "Will the unemployment rate be ≤3.9% in September?", "4.0": "Will the unemployment rate be 4.0% in September?", "high": "Will the unemployment rate be ≥4.1% in September?"}
    keys = ["le_3.90", "4.00", "gt_4.00"]
    kalshi_titles = ladder_bucket_titles(keys, step=0.1, subject="KXU3-26SEP ladder bucket")
    records = [
        _comparison("2026-10-01T13:40:00+00:00", "polymarket", {"low": 0.2, "4.0": 0.5, "high": 0.3}, {"low": 0.1, "4.0": 0.6, "high": 0.3}, poly_titles),
        _comparison("2026-10-01T13:40:00+00:00", "kalshi", {"le_3.90": 0.2, "4.00": 0.5, "gt_4.00": 0.3}, {"le_3.90": 0.3, "4.00": 0.4, "gt_4.00": 0.3}, kalshi_titles),
    ]
    assert set(final_record_per_release(records)) == {("2026-09", "polymarket"), ("2026-09", "kalshi")}
    card = score_unemployment_comparisons(records, realized={"2026-09": 4.0})
    assert card.scored_releases == 2
    assert {r.venue for r in card.records} == {"polymarket", "kalshi"}
    assert all(r.realized_bucket in ("4.0", "4.00") for r in card.records)
    current = card.to_dict()
    assert len(new_scored_records(None, current, "reference_period")) == 2
    previous = {"records": [r for r in current["records"] if r["venue"] == "polymarket"]}
    assert [r["venue"] for r in new_scored_records(previous, current, "reference_period")] == ["kalshi"]


def test_record_dataclass_carries_contract_series_default_none() -> None:
    fields = EventPriceRecord.__dataclass_fields__
    assert "contract_series" in fields and fields["contract_series"].default is None
