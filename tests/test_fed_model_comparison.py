import json
from pathlib import Path

from forecast_macro.datasets import load_fomc_history, scheduled_meetings
from forecast_macro.fed_model_comparison import run_walk_forward_logistic

ROOT = Path(__file__).parents[1]


def test_walk_forward_comparison_has_required_sample() -> None:
    meetings = scheduled_meetings(
        load_fomc_history(ROOT / "data" / "fomc_meetings_2019_2024.csv")
    )
    snapshots = json.loads(
        (ROOT / "data" / "generated" / "fomc_feature_snapshots_2019_2024.json").read_text()
    )

    report = run_walk_forward_logistic(meetings, snapshots)

    assert report.evaluated_meetings == 39
    assert report.non_zlb_evaluated_meetings == 23
    assert report.actual_cuts == 3
    assert 0.0 <= report.model_brier <= 1.0
    assert report.minimum_sample_required == 30
    assert report.climatology_gate_passed is False
    assert report.market_baseline_available is False
    assert report.signal_eligible is False
