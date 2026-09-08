"""Follow-ups from Claude review 4: R4-H2 window scope, R4-L1 sources, R4-L2, R4-L4."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from forecast_macro.datasets import (
    load_fomc_history,
    predetermined_window_dates,
    scheduled_meetings,
    validate_continuity,
    window_meetings,
)
from forecast_macro.fed_backtest import run_fed_baseline_backtest
from forecast_macro.fomc import RateDecision

ROOT = Path(__file__).parents[1]
MEETINGS = ROOT / "data" / "fomc_meetings_2019_2024.csv"
SNAPSHOTS = ROOT / "data" / "generated" / "fomc_feature_snapshots_2019_2024.json"


def test_every_decision_cites_its_own_press_release() -> None:
    for row in load_fomc_history(MEETINGS):
        stamp = row.meeting_at.strftime("%Y%m%d")
        assert row.source.endswith(f"/monetary{stamp}a.htm"), row.meeting_at


def test_generic_calendar_source_is_rejected(tmp_path: Path) -> None:
    text = MEETINGS.read_text().splitlines()
    header, first = text[0], text[1]
    generic = first.replace(
        first.rsplit(",", 1)[1], "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
    )
    path = tmp_path / "m.csv"
    path.write_text(f"{header}\n{generic}\n")
    with pytest.raises(ValueError, match="press release"):
        load_fomc_history(path)


def test_scheduled_scope_has_a_rate_gap_in_march_2020() -> None:
    scheduled = scheduled_meetings(load_fomc_history(MEETINGS))
    with pytest.raises(ValueError, match="discontinuity before 2020-04-29"):
        validate_continuity(scheduled)


def test_window_scope_attributes_emergency_cuts_to_the_next_scheduled_meeting() -> None:
    rows = load_fomc_history(MEETINGS)
    # The April 2020 window (-150bp) was decided by the March emergency cuts before any
    # prior-day forecast could be made, so it is reported and dropped rather than scored.
    assert [value.isoformat() for value in predetermined_window_dates(rows)] == ["2020-04-29"]
    window = window_meetings(rows)
    by_date = {row.meeting_at.date().isoformat(): row for row in window}
    assert len(window) == 46
    assert "2020-04-29" not in by_date
    assert by_date["2020-06-10"].decision is RateDecision.HOLD
    assert by_date["2020-06-10"].upper_before == 0.25
    assert by_date["2024-09-18"].change_bps == -50
    assert sum(row.decision is RateDecision.CUT for row in window) == 6  # 2019 x3, 2024 x3


def test_window_scope_backtest_runs_against_point_in_time_snapshots() -> None:
    window = window_meetings(load_fomc_history(MEETINGS))
    snapshots = json.loads(SNAPSHOTS.read_text())
    report = run_fed_baseline_backtest(window, snapshots)
    assert report.evaluated_meetings == 38
    assert report.actual_cuts == 3
    assert report.signal_eligible is False


@pytest.mark.parametrize(
    "scope, filename",
    [
        ("all", "fed_baseline_backtest_all_2019_2024.json"),
        ("window", "fed_baseline_backtest_window_2019_2024.json"),
    ],
)
def test_checked_in_backtests_reproduce(scope: str, filename: str) -> None:
    rows = load_fomc_history(MEETINGS)
    if scope == "window":
        rows = window_meetings(rows)
    report = run_fed_baseline_backtest(rows, json.loads(SNAPSHOTS.read_text())).to_dict()
    checked_in = json.loads((ROOT / "data" / "generated" / filename).read_text())
    script_only = {"event_scope", "dropped_predetermined_windows"}
    assert set(checked_in) - script_only == set(report)
    for key, value in checked_in.items():
        if key == "predictions" or key in script_only:
            continue
        if isinstance(value, float):
            assert report[key] == pytest.approx(value, abs=1e-9), key
        else:
            assert report[key] == value, key
    assert [p["probability_cut"] for p in checked_in["predictions"]] == pytest.approx(
        [p["probability_cut"] for p in report["predictions"]], abs=1e-9
    )


def test_scheduled_scope_script_refuses_gap_without_flag(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_fed_backtest.py"),
            "--meetings",
            str(MEETINGS),
            "--snapshots",
            str(SNAPSHOTS),
            "--output",
            str(tmp_path / "out.json"),
            "--event-scope",
            "scheduled",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=ROOT,
        env={"PYTHONPATH": str(ROOT / "src")},
    )
    assert result.returncode != 0
    assert "discontinuity before 2020-04-29" in result.stderr


def test_2019_2026_history_extends_the_fixture_without_gaps() -> None:
    rows = load_fomc_history(ROOT / "data" / "fomc_meetings_2019_2026.csv")
    fixture = load_fomc_history(MEETINGS)
    assert rows[: len(fixture)] == fixture
    assert len(rows) == 62
    validate_continuity(scheduled_meetings(rows[len(fixture) :]))
    assert rows[-1].upper_after == 3.75
    assert [r.meeting_at.date().isoformat() for r in rows if r.meeting_at.year == 2025 and r.decision is RateDecision.CUT] == [
        "2025-09-17",
        "2025-10-29",
        "2025-12-10",
    ]


@pytest.mark.parametrize(
    "scope, filename",
    [
        ("all", "fed_baseline_backtest_all_2019_2026.json"),
        ("window", "fed_baseline_backtest_window_2019_2026.json"),
    ],
)
def test_checked_in_2019_2026_backtests_reproduce(scope: str, filename: str) -> None:
    rows = load_fomc_history(ROOT / "data" / "fomc_meetings_2019_2026.csv")
    if scope == "window":
        rows = window_meetings(rows)
    snapshots = json.loads((ROOT / "data" / "generated" / "fomc_feature_snapshots_2019_2026.json").read_text())
    report = run_fed_baseline_backtest(rows, snapshots).to_dict()
    checked_in = json.loads((ROOT / "data" / "generated" / filename).read_text())
    for key, value in checked_in.items():
        if key in {"event_scope", "dropped_predetermined_windows", "predictions"}:
            continue
        if isinstance(value, float):
            assert report[key] == pytest.approx(value, abs=1e-9), key
        else:
            assert report[key] == value, key
