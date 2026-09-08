"""Task 44: the transcribed release calendar must reach at least 45 days ahead before the daily run starts."""
from __future__ import annotations

from datetime import UTC, datetime

from forecast_macro.release_schedule import ScheduledRelease, load_release_schedule
from forecast_macro.schedule_coverage import coverage, shortfalls


def _row(series: str, when: datetime) -> ScheduledRelease:
    return ScheduledRelease(series=series, reference_period="x", release_at=when, source_url="https://www.bls.gov/", fetched_at="t")


def test_short_and_missing_series_are_reported() -> None:
    now = datetime(2026, 9, 8, tzinfo=UTC)
    schedule = [_row("cpi", datetime(2026, 10, 14, tzinfo=UTC)), _row("fomc", datetime(2027, 6, 16, tzinfo=UTC))]
    reports = {r.series: r for r in coverage(schedule, as_of=now)}
    assert reports["cpi"].ok is False and reports["cpi"].days_ahead == 36
    assert reports["fomc"].ok is True
    assert reports["employment_situation"].last_release_at is None
    problems = shortfalls(list(reports.values()))
    assert any(p.startswith("cpi: calendar ends 2026-10-14") for p in problems)
    assert any(p.startswith("employment_situation: no future release") for p in problems)


def test_checked_in_calendar_covers_its_own_fetch_date_plus_45_days() -> None:
    schedule = load_release_schedule()
    fetched = max(datetime.fromisoformat(row.fetched_at) for row in schedule)
    assert all(r.ok for r in coverage(schedule, as_of=fetched))
