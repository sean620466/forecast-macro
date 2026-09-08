"""Task 17: empirical one-month-ahead unemployment bucket baseline vs the market (no signals)."""

from datetime import UTC, date, datetime

import pytest

from forecast_macro.models.unemployment import (
    MonthlyRate,
    RateBucket,
    monthly_change_distribution,
    next_month_bucket_probabilities,
    validate_buckets,
)
from forecast_macro.release_schedule import load_release_schedule
from forecast_macro.unemployment_comparison import (
    buckets_from_record,
    build_unemployment_comparison,
    next_employment_release,
)

# Priced Polymarket record for event 964993 (September 2026 unemployment), bot snapshot 2026-09-08.
RECORD = {
    "venue": "polymarket",
    "venue_event_id": "964993",
    "topic": "unemployment",
    "observed_at": "2026-09-08T02:44:39+00:00",
    "outcome_at": "2026-10-02T08:30:00-04:00",
    "contracts": {
        "4217153": "Will the September 2026 unemployment rate be ≤3.8%?",
        "4217154": "Will the September 2026 unemployment rate be 3.9%?",
        "4217155": "Will the September 2026 unemployment rate be 4.0%?",
        "4217156": "Will the September 2026 unemployment rate be 4.1%?",
        "4217157": "Will the September 2026 unemployment rate be 4.2%?",
        "4217158": "Will the September 2026 unemployment rate be 4.3%?",
        "4217159": "Will the September 2026 unemployment rate be 4.4%?",
        "4217160": "Will the September 2026 unemployment rate be 4.5%?",
        "4217161": "Will the September 2026 unemployment rate be ≥4.6%?",
    },
    "probabilities": {
        "4217153": 0.023, "4217154": 0.021, "4217155": 0.171, "4217156": 0.34, "4217157": 0.28,
        "4217158": 0.11, "4217159": 0.031, "4217160": 0.013, "4217161": 0.011,
    },
    "probability_bounds": {k: [0.0, 1.0] for k in ("4217153", "4217154", "4217155", "4217156", "4217157", "4217158", "4217159", "4217160", "4217161")},
}


def _history() -> list[MonthlyRate]:
    # 30 months: mostly flat with a few ±0.1/±0.2 moves and an unpublished month (Oct 2025).
    rows = []
    value = 4.0
    pattern = [0.0, 0.1, 0.0, -0.1, 0.0, 0.2, -0.1, 0.0, 0.0, 0.1, -0.2, 0.0]
    for index in range(30):
        year, month = divmod(2024 * 12 + 2 + index, 12)
        month += 1
        value = round(value + pattern[index % len(pattern)], 1)
        if (year, month) == (2025, 10):
            continue
        rows.append(MonthlyRate(month=date(year, month, 1), value=value))
    return rows


def test_change_distribution_skips_the_unpublished_month_and_sums_to_one() -> None:
    distribution = monthly_change_distribution(_history())
    assert sum(distribution.values()) == pytest.approx(1.0)
    assert set(distribution) <= {-0.2, -0.1, 0.0, 0.1, 0.2}
    # 29 rows, one gap (Sep->Nov 2025) removes two consecutive pairs: 26 changes counted.
    assert len(_history()) == 29


def test_buckets_from_titles_cover_the_space_and_probabilities_sum_to_one() -> None:
    buckets = buckets_from_record(RECORD)
    validate_buckets(buckets)
    assert {b.kind for b in buckets} == {"lower", "exact", "upper"}
    distribution = {-0.2: 0.1, -0.1: 0.25, 0.0: 0.3, 0.1: 0.25, 0.2: 0.1}
    probabilities = {p.outcome: p.probability for p in next_month_bucket_probabilities(4.1, distribution, buckets)}
    assert sum(probabilities.values()) == pytest.approx(1.0)
    assert probabilities["4217156"] == pytest.approx(0.3)  # 4.1 stays 4.1
    assert probabilities["4217154"] == pytest.approx(0.1)  # 4.1 - 0.2 = 3.9
    assert probabilities["4217153"] == 0.0 and probabilities["4217161"] == 0.0


def test_tail_buckets_absorb_large_moves_and_gaps_are_rejected() -> None:
    buckets = buckets_from_record(RECORD)
    distribution = {-2.2: 0.01, 0.0: 0.5, 10.4: 0.01, 0.1: 0.48}
    probabilities = {p.outcome: p.probability for p in next_month_bucket_probabilities(4.1, distribution, buckets)}
    assert probabilities["4217153"] == pytest.approx(0.01)
    assert probabilities["4217161"] == pytest.approx(0.01)
    with pytest.raises(ValueError, match="contiguous"):
        validate_buckets([b for b in buckets if b.value != 4.2])
    with pytest.raises(ValueError, match="lower tail"):
        validate_buckets([RateBucket("a", "exact", 4.0), RateBucket("b", "exact", 4.1)])


def test_comparison_record_matches_market_buckets_and_keeps_signals_off() -> None:
    schedule = load_release_schedule()
    as_of = datetime(2026, 9, 8, 13, 40, tzinfo=UTC)
    release = next_employment_release(schedule, as_of=as_of)
    assert release.release_at.isoformat() == "2026-10-02T08:30:00-04:00"
    comparison = build_unemployment_comparison(
        as_of=as_of, release=release, history=_history(), history_vintage="2026-09-08",
        record=RECORD, source_file="market_prices_x.json",
    )
    assert comparison.reference_period == "2026-09"
    assert set(comparison.model) == set(comparison.market) == set(comparison.edge)
    assert sum(comparison.model.values()) == pytest.approx(1.0)
    assert comparison.latest_month == "2026-08-01"  # last row of the synthetic history
    assert comparison.signal_eligible is False
    assert comparison.to_dict()["change_distribution"]["+0.0"] > 0
