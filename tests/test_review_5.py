"""Regression tests for Claude review 5 findings (R5-C1, R5-M5, R5-M6, R5-L1)."""

import json
from pathlib import Path

import pytest

from forecast_macro.datasets import load_fomc_history, scheduled_meetings
from forecast_macro.fed_backtest import run_fed_baseline_backtest
from forecast_macro.fed_model_comparison import run_walk_forward_logistic

ROOT = Path(__file__).parents[1]


def _scheduled_inputs() -> tuple[list, list[dict[str, object]]]:
    meetings = scheduled_meetings(
        load_fomc_history(ROOT / "data" / "fomc_meetings_2019_2024.csv")
    )
    snapshots = json.loads(
        (ROOT / "data" / "generated" / "fomc_feature_snapshots_2019_2024.json").read_text()
    )
    return meetings, snapshots


def test_walk_forward_reports_always_hold_and_intercept_ablation() -> None:
    meetings, snapshots = _scheduled_inputs()
    report = run_walk_forward_logistic(meetings, snapshots)

    # R5-M6: the harder baselines must be reported next to climatology.
    assert report.always_hold_brier == pytest.approx(3 / 39)
    assert report.brier_skill_vs_always_hold is not None
    assert 0.0 < report.intercept_only_brier < 1.0
    # R5-C1: the non-ZLB subset is where the model has to earn its skill.
    assert report.non_zlb_evaluated_meetings == 23
    assert report.non_zlb_model_brier is not None
    assert report.non_zlb_climatology_brier is not None
    assert report.non_zlb_always_hold_brier == pytest.approx(3 / 23)
    assert report.signal_eligible is False


def test_walk_forward_matches_checked_in_report() -> None:
    meetings, snapshots = _scheduled_inputs()
    report = run_walk_forward_logistic(meetings, snapshots).to_dict()
    checked_in = json.loads(
        (ROOT / "data" / "generated" / "fed_walk_forward_logistic_2019_2024.json").read_text()
    )
    assert set(checked_in) == set(report)
    for key, value in checked_in.items():
        if isinstance(value, float):
            assert report[key] == pytest.approx(value, abs=1e-9), key
        else:
            assert report[key] == value, key


def test_walk_forward_rejects_missing_snapshot() -> None:
    meetings, snapshots = _scheduled_inputs()
    with pytest.raises(ValueError, match="missing snapshots"):
        run_walk_forward_logistic(meetings, snapshots[:-1])


def test_walk_forward_rejects_policy_rate_mismatch() -> None:
    meetings, snapshots = _scheduled_inputs()
    # Index 0 is a scheduled meeting; emergency rows are filtered out and never checked.
    snapshots[0]["policy_rate_upper"] = 99
    with pytest.raises(ValueError, match="policy-rate snapshot mismatch"):
        run_walk_forward_logistic(meetings, snapshots)


def test_always_hold_skill_is_none_without_cuts() -> None:
    # R5-L1: a window with no cuts makes always-hold perfect, so the ratio is undefined.
    meetings = load_fomc_history(ROOT / "data" / "fomc_meetings_2022_2024.csv")
    snapshots = json.loads(
        (ROOT / "data" / "generated" / "fomc_feature_snapshots_2022_2024.json").read_text()
    )
    no_cut_meetings = [row for row in meetings if row.meeting_at.year < 2024]
    no_cut_snapshots = [row for row in snapshots if str(row["meeting_date"]) < "2024"]
    report = run_fed_baseline_backtest(no_cut_meetings, no_cut_snapshots, warmup=8)
    assert report.actual_cuts == 0
    assert report.always_hold_brier == 0.0
    assert report.brier_skill_vs_always_hold is None


def test_walk_forward_2019_2026_matches_checked_in_report_and_passes_sample_gate() -> None:
    meetings = scheduled_meetings(load_fomc_history(ROOT / "data" / "fomc_meetings_2019_2026.csv"))
    snapshots = json.loads(
        (ROOT / "data" / "generated" / "fomc_feature_snapshots_2019_2026.json").read_text()
    )
    report = run_walk_forward_logistic(meetings, snapshots).to_dict()
    checked_in = json.loads(
        (ROOT / "data" / "generated" / "fed_walk_forward_logistic_2019_2026.json").read_text()
    )
    for key, value in checked_in.items():
        if isinstance(value, float):
            assert report[key] == pytest.approx(value, abs=1e-9), key
        else:
            assert report[key] == value, key
    # D-013 sample floor is met for the first time; D-007 (market baseline) still is not.
    assert report["non_zlb_evaluated_meetings"] >= 30
    assert report["climatology_gate_passed"] is True
    assert report["market_baseline_available"] is False
    assert report["signal_eligible"] is False
