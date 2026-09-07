from datetime import UTC, datetime, timedelta

import pytest

from forecast_macro.contracts import (
    FedOutcome,
    PredictionContract,
    bucket_rate_change,
    normalize_outcome_prices,
)
from forecast_macro.transforms import month_over_month, rolling_change, year_over_year


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
    result = normalize_outcome_prices({"cut": 0.55, "hold": 0.50})
    assert sum(result.values()) == pytest.approx(1.0)
    assert result["cut"] == pytest.approx(0.55 / 1.05)


def test_market_prices_reject_incomplete_market():
    with pytest.raises(ValueError, match="complete market"):
        normalize_outcome_prices({"cut": 0.2, "hold": 0.2})


def test_contract_rejects_market_snapshot_after_meeting():
    meeting = datetime(2026, 9, 16, 18, tzinfo=UTC)
    with pytest.raises(ValueError, match="precede"):
        PredictionContract(
            contract_id="fed-2026-09",
            meeting_at=meeting,
            observed_at=meeting + timedelta(seconds=1),
            outcomes=("cut", "hold"),
        )
