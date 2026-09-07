from datetime import UTC
from pathlib import Path

import pytest

from forecast_macro.datasets import decision_counts, load_fomc_history
from forecast_macro.fomc import RateDecision

DATASET = Path(__file__).parents[1] / "data" / "fomc_meetings_2022_2024.csv"


def test_verified_fomc_dataset_loads_and_is_complete():
    rows = load_fomc_history(DATASET)
    assert len(rows) == 24
    assert rows[0].meeting_at.date().isoformat() == "2022-01-26"
    assert rows[-1].meeting_at.date().isoformat() == "2024-12-18"


def test_dataset_target_range_is_continuous_and_labeled():
    rows = load_fomc_history(DATASET)
    assert rows[0].upper_before == 0.25
    assert rows[-1].upper_after == 4.50
    counts = decision_counts(rows)
    assert counts[RateDecision.HIKE] == 11
    assert counts[RateDecision.HOLD] == 10
    assert counts[RateDecision.CUT] == 3


def test_dataset_decision_time_uses_dst():
    rows = load_fomc_history(DATASET)
    september = next(row for row in rows if row.meeting_at.date().isoformat() == "2024-09-18")
    december = rows[-1]
    assert september.meeting_at.astimezone(UTC).hour == 18
    assert december.meeting_at.astimezone(UTC).hour == 19


def test_loader_rejects_change_mismatch(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "meeting_date,decision_time_local,timezone,upper_before,upper_after,change_bps,decision,source\n"
        "2024-01-31,14:00,America/New_York,5.50,5.50,25,hold,"
        "https://www.federalreserve.gov/test\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="change_bps mismatch"):
        load_fomc_history(bad)
