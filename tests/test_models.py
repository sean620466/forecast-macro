import pytest

from forecast_macro.models.cpi import cpi_bucket_probabilities
from forecast_macro.models.fed import rate_cut_probability
from forecast_macro.signals import compare_to_market


def test_fed_probabilities_sum_to_one():
    result = rate_cut_probability(
        inflation_yoy=2.5,
        unemployment_rate=4.2,
        unemployment_change_3m=0.2,
        policy_rate=4.5,
    )
    assert sum(item.probability for item in result) == pytest.approx(1.0)


def test_cpi_probabilities_sum_to_one():
    result = cpi_bucket_probabilities(forecast_mom=0.25)
    assert sum(item.probability for item in result) == pytest.approx(1.0)
    assert all(0 <= item.probability <= 1 for item in result)


def test_signal_threshold():
    model = rate_cut_probability(
        inflation_yoy=2.0,
        unemployment_rate=4.5,
        unemployment_change_3m=0.5,
        policy_rate=5.0,
    )
    market = {"cut": 0.1, "hold_or_hike": 0.9}
    signals = compare_to_market(model, market, threshold=0.08)
    assert any(signal.should_display for signal in signals)
