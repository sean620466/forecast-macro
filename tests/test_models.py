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
    signals = compare_to_market(model, market, threshold=0.08, signal_eligible=True)
    assert any(signal.should_display for signal in signals)


def test_uncalibrated_model_never_displays_signal():
    model = rate_cut_probability(
        inflation_yoy=2.0,
        unemployment_rate=8.0,
        unemployment_change_3m=2.0,
        policy_rate=8.0,
    )
    market = {"cut": 0.01, "hold_or_hike": 0.99}
    assert not any(item.should_display for item in compare_to_market(model, market))


def test_cpi_rejects_invalid_bucket_order():
    with pytest.raises(ValueError, match="lower_cutoff"):
        cpi_bucket_probabilities(forecast_mom=0.2, lower_cutoff=0.4, upper_cutoff=0.3)


def test_cpi_rejects_nonpositive_uncertainty():
    with pytest.raises(ValueError, match="std"):
        cpi_bucket_probabilities(forecast_mom=0.2, uncertainty=0.0)


def test_fed_extreme_values_do_not_overflow():
    high = rate_cut_probability(
        inflation_yoy=-1_000_000,
        unemployment_rate=4.0,
        unemployment_change_3m=0.0,
        policy_rate=4.0,
    )
    low = rate_cut_probability(
        inflation_yoy=1_000_000,
        unemployment_rate=4.0,
        unemployment_change_3m=0.0,
        policy_rate=4.0,
    )
    assert high[0].probability == 1.0
    assert low[0].probability == 0.0
    assert sum(item.probability for item in high) == 1.0


def test_fed_rejects_nan():
    with pytest.raises(ValueError, match="finite"):
        rate_cut_probability(
            inflation_yoy=float("nan"),
            unemployment_rate=4.0,
            unemployment_change_3m=0.0,
            policy_rate=4.0,
        )
