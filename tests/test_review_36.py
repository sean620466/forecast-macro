"""Kalshi BLS ladders (KXU3, KXCPIYOY): 0.1-point rungs, reference-month calendar lookup."""

from datetime import UTC, datetime

from forecast_macro.market_discovery import kalshi_candidates
from forecast_macro.market_review import ReviewStatus, ladder_step_for, review_market_candidates
from forecast_macro.market_rules import identify_contract_series, parse_kalshi_rules
from forecast_macro.release_schedule import (
    load_release_schedule,
    parse_reference_month,
    verify_close_time,
)

NOW = datetime(2026, 9, 8, 17, 0, tzinfo=UTC)
U3_RULE = (
    "If the seasonally adjusted unemployment rate (U-3) reported by the Bureau of Labor Statistics in the "
    "Employment Situation Report is above {f}% in September 2026, then the market resolves to Yes."
)
CPI_RULE = (
    "If the Consumer Price Index (CPI) increases by more than {f}% in the twelve months ending August 2026 "
    "(as represented by the one-decimal place value reported by the Bureau of Labor Statistics), then the market resolves to Yes."
)


def _market(series: str, event: str, floor: float, rule: str, close: str) -> dict:
    return {
        "ticker": f"{series}-{event}-T{floor}",
        "event_ticker": f"{series}-{event}",
        "title": ("Will the unemployment rate (U-3) be above " if series == "KXU3" else "Will the rate of CPI inflation be above ") + f"{floor}% in the month?",
        "status": "active",
        "close_time": close,
        "floor_strike": floor,
        "strike_type": "greater",
        "yes_bid_dollars": "0.40",
        "yes_ask_dollars": "0.45",
        "rules_primary": rule.format(f=floor),
    }


def test_ladder_step_depends_on_topic() -> None:
    assert ladder_step_for("fed_rate") == 0.25
    assert ladder_step_for("unemployment") == 0.1 and ladder_step_for("cpi") == 0.1


def test_tenth_point_unemployment_ladder_validates_and_verifies_on_the_calendar() -> None:
    floors = [round(3.7 + 0.1 * i, 1) for i in range(14)]
    markets = [_market("KXU3", "26SEP", f, U3_RULE, "2026-10-02T12:29:00Z") for f in floors]
    rows = [c.to_dict() for c in kalshi_candidates({"markets": markets})]
    for row in rows:
        row["topic"] = "unemployment"
    reviews = review_market_candidates(rows)
    assert {r.status for r in reviews} == {ReviewStatus.RULES_REQUIRED}
    assert all("bucket structure complete" in r.checks_passed for r in reviews)

    document = parse_kalshi_rules(markets[0])
    assert identify_contract_series(document, topic="unemployment") == "unemployment_rate_sa"
    assert parse_reference_month(document.description) == "2026-09"
    close = verify_close_time(
        topic="unemployment", rule_text=document.description, venue_close_raw="2026-10-02T12:29:00Z",
        schedule=load_release_schedule(),
    )
    assert close.verified is True
    assert close.outcome_at.isoformat() == "2026-10-02T08:30:00-04:00"


def test_headline_cpi_yoy_ladder_identifies_as_nsa_yoy() -> None:
    market = _market("KXCPIYOY", "26AUG", 3.2, CPI_RULE, "2026-09-11T12:29:00Z")
    document = parse_kalshi_rules(market)
    assert identify_contract_series(document, topic="cpi") == "headline_cpi_yoy_nsa"
    assert parse_reference_month(document.description) == "2026-08"
    close = verify_close_time(
        topic="cpi", rule_text=document.description, venue_close_raw="2026-09-11T12:29:00Z",
        schedule=load_release_schedule(),
    )
    assert close.verified is True and close.outcome_at.isoformat() == "2026-09-11T08:30:00-04:00"
