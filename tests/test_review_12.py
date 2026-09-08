"""Task 12: Kalshi cumulative threshold ladders as exclusive buckets (R5-H2 residual)."""

from datetime import UTC, datetime

import pytest

from forecast_macro.contracts import normalize_threshold_ladder
from forecast_macro.data.kalshi import parse_kalshi_market_quote
from forecast_macro.market_discovery import kalshi_candidates
from forecast_macro.market_review import ReviewStatus, is_threshold_ladder, review_market_candidates
from forecast_macro.market_rules import (
    identify_contract_series,
    parse_kalshi_rules,
    validate_official_rules,
    verified_rule_metadata,
)
from forecast_macro.release_schedule import load_release_schedule, verify_close_time

NOW = datetime(2026, 9, 8, 2, 30, tzinfo=UTC)
# Live KXFED-26SEP top of book, 2026-09-08 02:30 UTC (YES = P(upper bound > floor)).
LIVE_LADDER = {
    2.75: (0.99, 1.00),
    3.00: (0.99, 1.00),
    3.25: (0.99, 1.00),
    3.50: (0.99, 1.00),
    3.75: (0.52, 0.53),
    4.00: (0.01, 0.02),
    4.25: (0.00, 0.01),
    4.50: (0.00, 0.01),
    4.75: (0.00, 0.01),
    5.00: (0.00, 0.01),
    5.25: (0.00, 0.01),
}
RULES_PRIMARY = (
    "If the upper bound of the target federal funds rate published on the Federal Reserve's "
    "official website is greater than 3.75% following the Federal Reserve's Sep 16, 2026 "
    "meeting, then the market resolves to Yes."
)
RULES_SECONDARY = (
    "This market will expire the first 2:05 PM ET following the release of a Federal Reserve "
    "statement for their Sep 16, 2026 meeting or one week following the last day of that meeting."
)


def _market(floor: float, bid: float, ask: float) -> dict:
    return {
        "ticker": f"KXFED-26SEP-T{floor:.2f}",
        "event_ticker": "KXFED-26SEP",
        "title": f"Will the upper bound of the federal funds rate be above {floor:.2f}% following the Fed's Sep 16, 2026 meeting?",
        "status": "active",
        "close_time": "2026-09-16T17:55:00Z",
        "floor_strike": floor,
        "strike_type": "greater",
        "yes_bid_dollars": f"{bid:.4f}",
        "yes_ask_dollars": f"{ask:.4f}",
        "yes_bid_size_fp": "100.00",
        "yes_ask_size_fp": "100.00",
        "rules_primary": RULES_PRIMARY,
        "rules_secondary": RULES_SECONDARY,
        "updated_time": "2026-09-08T02:00:00Z",
    }


def test_live_ladder_telescopes_into_exclusive_buckets() -> None:
    result = normalize_threshold_ladder(LIVE_LADDER)
    p = result.probabilities
    assert sum(p.values()) == pytest.approx(1.0, abs=1e-12)
    # Market-implied September decision: hold at 4.00 vs cut to 3.75.
    assert p["4.00"] == pytest.approx(0.51, abs=1e-9)  # (0.525 - 0.015)
    assert p["3.75"] == pytest.approx(0.47, abs=1e-9)  # (0.995 - 0.525)
    assert p["le_2.75"] == pytest.approx(0.005, abs=1e-9)
    assert p["gt_5.25"] == pytest.approx(0.005, abs=1e-9)
    assert result.lower_bounds["4.00"] == pytest.approx(0.52 - 0.02)
    assert result.upper_bounds["4.00"] == pytest.approx(0.53 - 0.01)
    for key in p:
        assert result.lower_bounds[key] - 1e-12 <= p[key] <= result.upper_bounds[key] + 1e-12, key


def test_ladder_rejects_gaps_and_inversions() -> None:
    with pytest.raises(ValueError, match="contiguous"):
        normalize_threshold_ladder({3.75: (0.5, 0.52), 4.25: (0.01, 0.02)})
    with pytest.raises(ValueError, match="not monotone"):
        normalize_threshold_ladder({3.75: (0.10, 0.12), 4.00: (0.50, 0.52)})
    with pytest.raises(ValueError, match="at least two"):
        normalize_threshold_ladder({3.75: (0.5, 0.52)})


def test_kalshi_discovery_keeps_strike_and_review_validates_ladder() -> None:
    payload = {"markets": [_market(f, b, a) for f, (b, a) in LIVE_LADDER.items()]}
    candidates = kalshi_candidates(payload)
    assert len(candidates) == 11
    assert candidates[0].strike == 2.75 and candidates[0].strike_type == "greater"
    rows = [c.to_dict() for c in candidates]
    assert is_threshold_ladder(rows)
    reviews = review_market_candidates(rows)
    assert {r.status for r in reviews} == {ReviewStatus.RULES_REQUIRED}
    assert all("bucket structure complete" in r.checks_passed for r in reviews)

    gapped = [row for row in rows if row["strike"] != 4.0]
    assert all(
        "ladder rungs are not contiguous in 0.25 steps" in r.blockers
        for r in review_market_candidates(gapped)
    )


def test_kalshi_rules_verify_against_fed_source_and_calendar() -> None:
    document = parse_kalshi_rules(_market(3.75, 0.52, 0.53), fetched_at=NOW)
    assert document.resolution_source == "https://www.federalreserve.gov/"
    assert document.rules_source_level == "market"
    assert identify_contract_series(document, topic="fed_rate") == "federal_funds_target_range"
    assert validate_official_rules(document, topic="fed_rate", expected_series="federal_funds_target_range") == ()
    metadata = verified_rule_metadata(document, topic="fed_rate", expected_series="federal_funds_target_range")
    assert metadata is not None and metadata.resolution_source_origin == "field"

    close = verify_close_time(
        topic="fed_rate",
        rule_text=document.description,
        venue_close_raw="2026-09-16T17:55:00Z",
        schedule=load_release_schedule(),
    )
    assert close.verified is True
    assert close.outcome_at.isoformat() == "2026-09-16T14:00:00-04:00"


def test_kalshi_rules_without_recognized_source_phrase_stay_locked() -> None:
    market = _market(3.75, 0.52, 0.53)
    market["rules_primary"] = "Resolves per a data vendor's federal funds rate feed."
    document = parse_kalshi_rules(market, fetched_at=NOW)
    assert document.resolution_source == ""
    assert verified_rule_metadata(document, topic="fed_rate") is None


def test_kalshi_market_quote_reads_dollar_fields() -> None:
    quote = parse_kalshi_market_quote(_market(3.75, 0.52, 0.53), observed_at=NOW)
    assert (quote.bid, quote.ask, quote.bid_size) == (0.52, 0.53, 100.0)
    assert quote.venue_contract_id == "KXFED-26SEP-T3.75"
