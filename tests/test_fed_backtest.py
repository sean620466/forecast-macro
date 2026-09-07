import json
from pathlib import Path

import pytest

from forecast_macro.datasets import load_fomc_history
from forecast_macro.fed_backtest import run_fed_baseline_backtest

ROOT = Path(__file__).parents[1]


def test_real_vintage_dataset_runs_without_signal_eligibility():
    meetings = load_fomc_history(ROOT / "data" / "fomc_meetings_2022_2024.csv")
    snapshots = json.loads(
        (ROOT / "data" / "generated" / "fomc_feature_snapshots_2022_2024.json").read_text()
    )
    report = run_fed_baseline_backtest(meetings, snapshots)
    assert report.total_meetings == 24
    assert report.evaluated_meetings == 16
    assert report.actual_cuts == 3
    assert report.constant_50_brier == pytest.approx(0.25)
    assert not report.signal_eligible
    assert len(report.predictions) == 16


def test_backtest_rejects_missing_snapshot():
    meetings = load_fomc_history(ROOT / "data" / "fomc_meetings_2022_2024.csv")
    snapshots = json.loads(
        (ROOT / "data" / "generated" / "fomc_feature_snapshots_2022_2024.json").read_text()
    )
    with pytest.raises(ValueError, match="missing snapshots"):
        run_fed_baseline_backtest(meetings, snapshots[:-1])


def test_backtest_rejects_policy_rate_mismatch():
    meetings = load_fomc_history(ROOT / "data" / "fomc_meetings_2022_2024.csv")
    snapshots = json.loads(
        (ROOT / "data" / "generated" / "fomc_feature_snapshots_2022_2024.json").read_text()
    )
    snapshots[8]["policy_rate_upper"] = 99
    with pytest.raises(ValueError, match="policy-rate snapshot mismatch"):
        run_fed_baseline_backtest(meetings, snapshots)
