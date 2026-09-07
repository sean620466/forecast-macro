import pytest

from forecast_macro.models.logistic import fit_logistic


def test_logistic_learns_ordered_signal() -> None:
    model = fit_logistic(
        [(-2.0,), (-1.0,), (1.0,), (2.0,)],
        [0, 0, 1, 1],
        ridge_strength=0.1,
    )

    assert model.predict((-1.5,)) < 0.5
    assert model.predict((1.5,)) > 0.5


def test_logistic_rejects_invalid_shapes() -> None:
    with pytest.raises(ValueError, match="aligned"):
        fit_logistic([(1.0,)], [])
