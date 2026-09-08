"""Task 39: 2015–2026 backtests reproduce, and the longer sample removes the reported skill."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from forecast_macro.datasets import load_fomc_history, scheduled_meetings, window_meetings
from forecast_macro.fed_backtest import run_fed_baseline_backtest
from forecast_macro.fed_model_comparison import run_walk_forward_logistic

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "data" / "generated"


def _snapshots(name: str) -> list[dict]:
    return json.loads((GENERATED / name).read_text())


def test_2015_2026_snapshots_agree_with_the_2019_2026_fixture_on_overlap() -> None:
    new = {row["meeting_date"]: row for row in _snapshots("fomc_feature_snapshots_2015_2026.json")}
    old = _snapshots("fomc_feature_snapshots_2019_2026.json")
    assert len(new) == 94 and len(old) == 62
    keys = ("vintage_date", "cpi_yoy_nsa", "unemployment_rate", "unemployment_change_3m", "policy_rate_upper", "data_gaps")
    for row in old:
        for key in keys:
            assert new[row["meeting_date"]][key] == row[key], (row["meeting_date"], key)
    first = new["2015-01-28"]
    assert first["vintage_date"] == "2015-01-27" and first["policy_rate_upper"] == 0.25
    assert first["inputs"]["cpi_latest"]["observed_at"] == "2014-12-01"


def _assert_close(actual, expected, key="") -> None:
    """Recursive comparison; floats approximate (Python 3.11 and 3.12 differ in the last digit)."""
    if isinstance(expected, float):
        assert actual == pytest.approx(expected, abs=1e-9), key
    elif isinstance(expected, dict):
        assert set(actual) == set(expected), key
        for k, v in expected.items():
            _assert_close(actual[k], v, f"{key}.{k}")
    elif isinstance(expected, list):
        assert len(actual) == len(expected), key
        for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
            _assert_close(a, e, f"{key}[{i}]")
    else:
        assert actual == expected, key


def _assert_matches(report: dict, checked_in: dict, skip=()) -> None:
    for key, value in checked_in.items():
        if key not in skip:
            _assert_close(report[key], value, key)


def test_walk_forward_2015_2026_reproduces_and_shows_little_skill() -> None:
    meetings = scheduled_meetings(load_fomc_history(ROOT / "data" / "fomc_meetings_2015_2026.csv"))
    report = run_walk_forward_logistic(meetings, _snapshots("fomc_feature_snapshots_2015_2026.json")).to_dict()
    _assert_matches(report, json.loads((GENERATED / "fed_walk_forward_logistic_2015_2026.json").read_text()))
    assert report["evaluated_meetings"] == 84 and report["non_zlb_evaluated_meetings"] == 68
    assert report["actual_cuts"] == 9 and report["actual_hikes"] == 19
    # R39-H1: the 2019–2026 skill (+0.17) does not survive the longer sample.
    assert 0.0 < report["brier_skill_vs_climatology"] < 0.05
    assert abs(report["non_zlb_brier_skill_vs_climatology"]) < 0.02
    assert report["climatology_gate_passed"] is True
    assert report["signal_eligible"] is False
    assert len(report["predictions"]) == 84


def test_more_history_is_worse_on_the_common_meetings() -> None:
    by_date = lambda name: {r["meeting_date"]: r for r in json.loads((GENERATED / name).read_text())["predictions"]}
    short, long = by_date("fed_walk_forward_logistic_2019_2026.json"), by_date("fed_walk_forward_logistic_2015_2026.json")
    common = sorted(set(short) & set(long))
    assert len(common) == 52 and common[0] == "2020-01-29"

    def three_way(rows):
        total = 0.0
        for date in common:
            r = rows[date]
            total += sum((r[k] - (r["outcome"] == k)) ** 2 for k in ("cut", "hold", "hike"))
        return total / len(common)

    assert three_way(long) > three_way(short)
    assert three_way(long) == pytest.approx(0.4205, abs=5e-4)
    assert three_way(short) == pytest.approx(0.3674, abs=5e-4)


@pytest.mark.parametrize(
    "scope, filename",
    [("all", "fed_baseline_backtest_all_2015_2026.json"), ("window", "fed_baseline_backtest_window_2015_2026.json")],
)
def test_checked_in_2015_2026_heuristic_backtests_reproduce(scope: str, filename: str) -> None:
    rows = load_fomc_history(ROOT / "data" / "fomc_meetings_2015_2026.csv")
    if scope == "window":
        rows = window_meetings(rows)
    report = run_fed_baseline_backtest(rows, _snapshots("fomc_feature_snapshots_2015_2026.json")).to_dict()
    checked_in = json.loads((GENERATED / filename).read_text())
    _assert_matches(report, checked_in, skip={"event_scope", "dropped_predetermined_windows", "predictions"})
    if scope == "window":
        assert report["brier_skill_vs_climatology"] < 0
        assert report["passes_climatology_gate"] is False
