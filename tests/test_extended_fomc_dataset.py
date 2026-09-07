from pathlib import Path

from forecast_macro.datasets import FomcEventType, load_fomc_history, scheduled_meetings
from forecast_macro.fomc import RateDecision

DATASET = Path(__file__).parents[1] / "data" / "fomc_meetings_2019_2024.csv"


def test_extended_history_has_expected_decisions() -> None:
    rows = load_fomc_history(DATASET)

    assert len(rows) == 49
    assert rows[0].meeting_at.date().isoformat() == "2019-01-30"
    assert rows[-1].meeting_at.date().isoformat() == "2024-12-18"
    assert sum(row.decision is RateDecision.CUT for row in rows) == 8


def test_emergency_decisions_are_explicit() -> None:
    rows = load_fomc_history(DATASET)
    emergencies = [row for row in rows if row.event_type is FomcEventType.EMERGENCY]

    assert [(row.meeting_at.date().isoformat(), row.change_bps) for row in emergencies] == [
        ("2020-03-03", -50),
        ("2020-03-15", -100),
    ]
    assert len(scheduled_meetings(rows)) == 47


def test_legacy_dataset_defaults_to_scheduled() -> None:
    legacy = DATASET.with_name("fomc_meetings_2022_2024.csv")
    rows = load_fomc_history(legacy)

    assert all(row.event_type is FomcEventType.SCHEDULED for row in rows)
