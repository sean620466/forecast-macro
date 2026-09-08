"""Task 41 (R35-M1): base-effect CPI YoY baseline and the research backtest against the empirical-change baseline."""
from __future__ import annotations

from datetime import date

import pytest

from forecast_macro.cpi_backtest import backtest_cpi_baselines, bucket_grid
from forecast_macro.models.cpi_base_effect import (
    base_effect_bucket_probabilities,
    base_effect_yoy_distribution,
    published_yoy,
    same_month_mom_history,
)
from forecast_macro.models.unemployment import MonthlyRate, validate_buckets

# Synthetic NSA index: 3% annual trend plus a fixed seasonal pattern, so every calendar month
# has a stable MoM and the base effect is the whole story.
SEASONAL = [0.4, 0.5, 0.6, 0.3, 0.2, 0.1, 0.0, 0.2, 0.3, 0.1, -0.2, -0.3]  # percent MoM by month


def _hash_noise(year: int, month: int) -> float:
    """Deterministic pseudo-random MoM noise in [-0.25, 0.25] pp with no year-to-year structure."""
    return ((year * 31 + month * 17) * 2654435761 % 1000) / 1000 - 0.5


def _levels(years: int = 20, start_year: int = 2000, noise=None) -> list[MonthlyRate]:
    rows, level = [], 100.0
    for year in range(start_year, start_year + years):
        for month in range(1, 13):
            mom = SEASONAL[month - 1] + (noise(year, month) if noise else 0.0)
            level *= 1 + mom / 100
            rows.append(MonthlyRate(month=date(year, month, 1), value=round(level, 3)))
    return rows


def test_same_month_history_uses_only_the_target_calendar_month() -> None:
    rows = _levels()
    levels = {r.month.year * 12 + r.month.month: r.value for r in rows}
    samples = same_month_mom_history(levels, target=date(2020, 1, 1))
    years = [y for y, _ in samples]
    assert years == list(range(2001, 2020))  # January 2000 has no December 1999 before it
    assert all(abs(m * 100 - 0.4) < 0.01 for _, m in samples)  # levels are rounded to 3 decimals


def test_base_effect_distribution_is_exact_when_seasonality_is_deterministic() -> None:
    rows = _levels()
    target, distribution = base_effect_yoy_distribution(rows)
    assert target == date(2020, 1, 1)
    # With a fixed seasonal pattern the YoY is the annual sum of MoMs (compounded), one value only.
    assert len(distribution) == 1 and abs(sum(distribution.values()) - 1.0) < 1e-12
    (yoy,) = distribution
    levels = {r.month.year * 12 + r.month.month: r.value for r in rows}
    assert yoy == pytest.approx(published_yoy(levels, date(2019, 12, 1)), abs=0.1)


def test_distribution_spreads_with_noisy_months_and_feeds_buckets() -> None:
    rows = _levels(noise=_hash_noise)
    _target, distribution = base_effect_yoy_distribution(rows)
    assert len(distribution) >= 3
    _t2, same = base_effect_yoy_distribution(rows, method="same_month")
    assert len(same) >= 3 and len(same) <= len(distribution)
    with pytest.raises(ValueError, match="method"):
        base_effect_yoy_distribution(rows, method="magic")
    latest = published_yoy({r.month.year * 12 + r.month.month: r.value for r in rows}, rows[-1].month)
    buckets = bucket_grid(latest)
    validate_buckets(buckets)
    probabilities = base_effect_bucket_probabilities(rows, buckets)
    assert sum(p.probability for p in probabilities) == pytest.approx(1.0)


def test_requires_enough_years_and_the_base_level() -> None:
    with pytest.raises(ValueError, match="at least 10"):
        base_effect_yoy_distribution(_levels(years=5))
    with pytest.raises(ValueError, match="eleven months"):
        base_effect_yoy_distribution(_levels()[-6:])


def test_backtest_scores_both_baselines_on_the_same_grid() -> None:
    rows = _levels(years=26, noise=_hash_noise)
    report = backtest_cpi_baselines(rows, series_id="SYNTH", start=date(2015, 1, 1))
    assert report.months == 11 * 12
    assert report.signal_eligible is False
    assert report.empirical_change_brier is not None and report.base_effect_brier is not None
    assert report.base_effect_wins + report.empirical_change_wins <= report.months
    record = report.records[0]
    assert record.target_month == "2015-01" and record.realized_bucket in {b.key for b in bucket_grid(record.latest_yoy)}
    # The base is known exactly, so the base-effect model only carries one month of noise while
    # the YoY-change model carries two (the new month and the month that drops out).
    assert report.base_effect_brier < report.empirical_change_brier
    assert report.base_effect_skill_vs_empirical_change > 0
    assert report.same_month_brier is not None


def test_change_distribution_override_reaches_the_comparison_builder() -> None:
    from datetime import UTC, datetime

    from forecast_macro.models.core_cpi import (
        BASE_EFFECT_MEASURES,
        CPI_MEASURES,
        core_cpi_yoy_history,
    )
    from forecast_macro.models.cpi_base_effect import base_effect_change_distribution
    from forecast_macro.release_schedule import ScheduledRelease
    from forecast_macro.unemployment_comparison import build_unemployment_comparison

    assert BASE_EFFECT_MEASURES == {"headline"} and "base-effect" in CPI_MEASURES["headline"][1]
    levels = _levels(noise=_hash_noise)
    history = core_cpi_yoy_history(levels)
    latest = history[-1].value
    changes = base_effect_change_distribution(levels, latest_yoy=latest)
    assert sum(changes.values()) == pytest.approx(1.0)
    keys = ["le_1.90", "2.00", "2.10", "2.20", "2.30", "gt_2.30"]
    record = {
        "venue": "kalshi",
        "venue_event_id": "KXCPIYOY-TEST",
        "topic": "cpi",
        "probabilities": dict.fromkeys(keys, 1 / 6),
        "probability_bounds": {k: [0.1, 0.2] for k in keys},
        "contracts": {},
        "observed_at": "2020-01-05T00:00:00+00:00",
    }
    release = ScheduledRelease(series="cpi", reference_period="2020-01", release_at=datetime(2020, 2, 12, 13, 30, tzinfo=UTC), source_url="https://www.bls.gov/schedule", fetched_at="2020-01-05")
    rec = build_unemployment_comparison(
        as_of=datetime(2020, 1, 5, tzinfo=UTC),
        release=release,
        history=history,
        history_vintage="2020-01-05",
        record=record,
        source_file="x.json",
        model_version="test",
        topic="cpi",
        change_distribution=changes,
    )
    assert rec.change_distribution == {f"{c:+.1f}": p for c, p in changes.items()}
    assert sum(rec.model.values()) == pytest.approx(1.0)


def test_checked_in_backtest_is_internally_consistent() -> None:
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "data" / "generated" / "cpi_baseline_backtest.json"
    payload = json.loads(path.read_text())
    for report in payload["measures"].values():
        assert report["months"] == len(report["records"]) >= 300
        assert report["base_effect_wins"] + report["empirical_change_wins"] <= report["months"]
        assert report["signal_eligible"] is False
    assert payload["measures"]["headline"]["base_effect_skill_vs_empirical_change"] > 0
    assert payload["measures"]["core"]["base_effect_skill_vs_empirical_change"] < 0
