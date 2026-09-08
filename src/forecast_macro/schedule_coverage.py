"""Release-calendar coverage check (task 44, R7-M1).

BLS refuses scripted downloads of its release calendar, so `data/release_schedule.csv` is
transcribed by hand. Every comparison script fails closed when the next release is missing,
but that failure would arrive on the day it is needed. This check runs first in the daily
workflow and fails while there is still time to transcribe the next months.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from forecast_macro.release_schedule import ScheduledRelease

REQUIRED_SERIES = ("cpi", "employment_situation", "fomc")
MINIMUM_DAYS_AHEAD = 45


@dataclass(frozen=True)
class CoverageReport:
    series: str
    last_release_at: str | None
    days_ahead: int | None
    ok: bool


def coverage(
    schedule: Sequence[ScheduledRelease],
    *,
    as_of: datetime,
    minimum_days: int = MINIMUM_DAYS_AHEAD,
    series: Sequence[str] = REQUIRED_SERIES,
) -> list[CoverageReport]:
    reports: list[CoverageReport] = []
    for name in series:
        future = [row.release_at for row in schedule if row.series == name and row.release_at > as_of]
        if not future:
            reports.append(CoverageReport(name, None, None, False))
            continue
        last = max(future)
        days = (last - as_of) // timedelta(days=1)
        reports.append(CoverageReport(name, last.isoformat(), days, days >= minimum_days))
    return reports


def shortfalls(reports: Sequence[CoverageReport]) -> list[str]:
    out: list[str] = []
    for report in reports:
        if report.ok:
            continue
        if report.last_release_at is None:
            out.append(f"{report.series}: no future release in data/release_schedule.csv")
        else:
            out.append(
                f"{report.series}: calendar ends {report.last_release_at[:10]} ({report.days_ahead} days ahead; "
                f"need {MINIMUM_DAYS_AHEAD})"
            )
    return out
