"""Task 19: venue fee schedules and net edge (D-003)."""

import pytest

from forecast_macro.fees import FEE_SCHEDULES, fee_summary, kalshi_fee_schedule_id, schedule_for


def test_polymarket_economics_fee_matches_published_table() -> None:
    schedule = schedule_for("polymarket-economics")
    assert schedule is not None and schedule.verified
    # Economics taker rate 0.05: $1.25 per 100 shares at 50c (the $1.75 table is the Crypto tab).
    assert schedule.taker_fee(0.50) * 100 == pytest.approx(1.25)
    assert schedule.taker_fee(0.10) * 100 == pytest.approx(0.45)  # 0.05 * 0.1 * 0.9 * 100
    assert schedule.taker_fee(0.25) * 100 == pytest.approx(0.9375)
    assert schedule.break_even_probability(0.34) == pytest.approx(0.34 + 0.05 * 0.34 * 0.66)
    assert schedule.net_edge(0.40, 0.34) == pytest.approx(0.40 - 0.34 - 0.05 * 0.34 * 0.66)


def test_kalshi_schedule_is_marked_unverified_and_rounds_up() -> None:
    assert kalshi_fee_schedule_id("quadratic_with_maker_fees", 1) == "kalshi-quadratic_with_maker_fees-x1"
    schedule = schedule_for("kalshi-quadratic_with_maker_fees-x1")
    assert schedule is not None and schedule.verified is False
    assert schedule.taker_fee(0.53) == pytest.approx(0.02)  # 0.07*0.53*0.47 = 0.0174 -> 2c
    assert schedule.taker_fee(0.01) == pytest.approx(0.01)  # never below one cent when nonzero


def test_unknown_schedule_is_reported_not_guessed() -> None:
    summary = fee_summary("polymarket-current-unknown", 0.5)
    assert summary == {"fee_schedule_id": "polymarket-current-unknown", "known": False}
    known = fee_summary("polymarket-economics", 0.5)
    assert known["known"] and known["verified"] and known["break_even_probability"] == pytest.approx(0.5125)
    assert all(s.source_url.startswith("https://") and s.fetched_at for s in FEE_SCHEDULES.values())
