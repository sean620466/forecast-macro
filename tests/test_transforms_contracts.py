from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from forecast_macro.contracts import (
    FedOutcome,
    PredictionContract,
    bucket_rate_change,
    fomc_decision_time,
    normalize_outcome_prices,
)
from forecast_macro.transforms import (
    CpiSeries,
    MonthlyIndex,
    cpi_mom,
    cpi_yoy,
    month_over_month,
    rolling_change,
    round_bls_tenth,
    year_over_year,
)


def test_cpi_month_over_month_from_index():
    assert month_over_month([300.0, 300.9]) == pytest.approx(0.3)


def test_cpi_year_over_year_from_index():
    values = [300.0] + [301.0] * 11 + [309.0]
    assert year_over_year(values) == pytest.approx(3.0)


def test_transforms_reject_invalid_history_and_denominator():
    with pytest.raises(ValueError, match="exactly 13"):
        year_over_year([100.0, 101.0])
    with pytest.raises(ValueError, match="positive"):
        month_over_month([0.0, 1.0])
    with pytest.raises(ValueError, match="exactly 4"):
        rolling_change([4.0, 4.1], periods=3)


@pytest.mark.parametrize(
    ("change_bps", "expected"),
    [
        (25, FedOutcome.HIKE),
        (0, FedOutcome.HOLD),
        (-25, FedOutcome.CUT_25),
        (-50, FedOutcome.CUT_50_PLUS),
        (-75, FedOutcome.CUT_50_PLUS),
    ],
)
def test_rate_change_contract_buckets(change_bps, expected):
    assert bucket_rate_change(change_bps) is expected


def test_market_prices_are_normalized():
    result = normalize_outcome_prices({"cut": 0.53, "hold": 0.50})
    assert sum(result.values()) == pytest.approx(1.0)
    assert result["cut"] == pytest.approx(0.53 / 1.03)


def test_market_prices_reject_incomplete_market():
    with pytest.raises(ValueError, match="complete market"):
        normalize_outcome_prices({"cut": 0.2, "hold": 0.2})


def test_contract_rejects_market_snapshot_after_meeting():
    meeting = datetime(2026, 9, 16, 18, tzinfo=UTC)
    with pytest.raises(ValueError, match="precede"):
        PredictionContract(
            contract_id="fed-2026-09",
            meeting_at=meeting,
            closes_at=meeting,
            observed_at=meeting + timedelta(seconds=1),
            outcomes=("cut", "hold"),
        )


def test_contract_rejects_naive_timestamps():
    meeting = datetime(2026, 12, 16, 14)  # noqa: DTZ001 - deliberately naive
    with pytest.raises(ValueError, match="timezone-aware"):
        PredictionContract("fed", meeting, meeting, meeting, ("cut", "hold"))


def test_fomc_time_observes_dst():
    eastern = ZoneInfo("America/New_York")
    assert fomc_decision_time(date(2026, 9, 16)).astimezone(UTC).hour == 18
    assert fomc_decision_time(date(2026, 12, 16)).astimezone(UTC).hour == 19
    assert fomc_decision_time(date(2026, 12, 16)).tzinfo == eastern


def test_complete_outcome_set_is_required():
    with pytest.raises(ValueError, match="complete contract"):
        normalize_outcome_prices(
            {"hold": 0.5, "cut_25": 0.5},
            expected_outcomes=("hike", "hold", "cut_25", "cut_50_plus"),
        )


def test_large_overround_is_rejected():
    with pytest.raises(ValueError, match="complete market"):
        normalize_outcome_prices({"cut": 0.60, "hold": 0.55})


def test_dated_cpi_transforms_and_rounding():
    mom = [MonthlyIndex(date(2026, 1, 1), 300), MonthlyIndex(date(2026, 2, 1), 300.9)]
    assert round_bls_tenth(cpi_mom(mom, series_id=CpiSeries.SA)) == 0.3
    yoy = [MonthlyIndex(date(2025 + (m // 12), m % 12 + 1, 1), 300 + m) for m in range(13)]
    assert cpi_yoy(yoy, series_id=CpiSeries.NSA) == pytest.approx(4.0)


def test_cpi_rejects_missing_month_and_wrong_series():
    gap = [MonthlyIndex(date(2026, 1, 1), 300), MonthlyIndex(date(2026, 3, 1), 301)]
    with pytest.raises(ValueError, match="consecutive"):
        cpi_mom(gap, series_id=CpiSeries.SA)
    with pytest.raises(ValueError, match="seasonally adjusted"):
        cpi_mom(gap, series_id=CpiSeries.NSA)
