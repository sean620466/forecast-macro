from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from datetime import date, datetime, time
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from zoneinfo import ZoneInfo

from forecast_macro.fomc import RateDecision, label_rate_decision

_PRESS_RELEASE = "https://www.federalreserve.gov/newsevents/pressreleases/monetary{stamp}a.htm"


class FomcEventType(StrEnum):
    SCHEDULED = "scheduled"
    EMERGENCY = "emergency"


@dataclass(frozen=True)
class HistoricalFomcRow:
    meeting_at: datetime
    upper_before: float
    upper_after: float
    change_bps: int
    decision: RateDecision
    source: str
    event_type: FomcEventType = FomcEventType.SCHEDULED


def load_fomc_history(path: str | Path) -> list[HistoricalFomcRow]:
    rows: list[HistoricalFomcRow] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            meeting_at = datetime.combine(
                date.fromisoformat(raw["meeting_date"]),
                time.fromisoformat(raw["decision_time_local"]),
                tzinfo=ZoneInfo(raw["timezone"]),
            )
            before = float(raw["upper_before"])
            after = float(raw["upper_after"])
            change_bps = int(raw["change_bps"])
            decision = RateDecision(raw["decision"])
            event_type = FomcEventType(raw.get("event_type") or "scheduled")
            calculated_change = round((after - before) * 100)
            if change_bps != calculated_change:
                raise ValueError(f"change_bps mismatch for {meeting_at.date()}")
            if decision is not label_rate_decision(upper_before=before, upper_after=after):
                raise ValueError(f"decision mismatch for {meeting_at.date()}")
            if not raw["source"].startswith("https://www.federalreserve.gov/"):
                raise ValueError("FOMC history requires a Federal Reserve source")
            # D-002 traceability: each decision cites its own press release, not a calendar page.
            expected_source = _PRESS_RELEASE.format(stamp=meeting_at.strftime("%Y%m%d"))
            if raw["source"] != expected_source:
                raise ValueError(
                    f"source for {meeting_at.date()} must be the decision press release {expected_source}"
                )
            rows.append(
                HistoricalFomcRow(
                    meeting_at=meeting_at,
                    upper_before=before,
                    upper_after=after,
                    change_bps=change_bps,
                    decision=decision,
                    source=raw["source"],
                    event_type=event_type,
                )
            )

    if not rows:
        raise ValueError("FOMC history is empty")
    if [row.meeting_at for row in rows] != sorted(row.meeting_at for row in rows):
        raise ValueError("FOMC history must be chronological")
    for previous, current in pairwise(rows):
        if previous.upper_after != current.upper_before:
            raise ValueError(f"target range discontinuity before {current.meeting_at.date()}")
    return rows


def decision_counts(rows: list[HistoricalFomcRow]) -> dict[RateDecision, int]:
    return {decision: sum(row.decision is decision for row in rows) for decision in RateDecision}


def scheduled_meetings(rows: list[HistoricalFomcRow]) -> list[HistoricalFomcRow]:
    return [row for row in rows if row.event_type is FomcEventType.SCHEDULED]


def validate_continuity(rows: list[HistoricalFomcRow]) -> None:
    """Every row's upper_before must equal the previous row's upper_after."""
    for previous, current in pairwise(rows):
        if previous.upper_after != current.upper_before:
            raise ValueError(f"target range discontinuity before {current.meeting_at.date()}")


def predetermined_window_dates(rows: list[HistoricalFomcRow]) -> list[date]:
    """Scheduled meetings whose window outcome was already fixed by an emergency move.

    When the rate entering a scheduled meeting differs from the previous scheduled decision,
    a forecast made at the prior-day cutoff already knows the window's direction. Scoring such
    a row would reward hindsight, so window scope drops it and reports the date.
    """
    scheduled = scheduled_meetings(rows)
    return [
        current.meeting_at.date()
        for previous, current in pairwise(scheduled)
        if current.upper_before != previous.upper_after
    ]


def window_meetings(rows: list[HistoricalFomcRow]) -> list[HistoricalFomcRow]:
    """Scheduled meetings labelled by the change since the previous *scheduled* decision.

    This matches how rate contracts settle ("target range after the <date> meeting"): an
    emergency move between two scheduled meetings is attributed to the window, not silently
    dropped (R4-H2). Windows whose outcome was predetermined before the forecast cutoff are
    excluded (see predetermined_window_dates); upper_before stays the actual rate entering
    the meeting so point-in-time snapshots still reconcile.
    """
    scheduled = scheduled_meetings(rows)
    predetermined = set(predetermined_window_dates(rows))
    result: list[HistoricalFomcRow] = []
    for index, row in enumerate(scheduled):
        if index == 0:
            result.append(row)
            continue
        if row.meeting_at.date() in predetermined:
            continue
        window_start = scheduled[index - 1].upper_after
        change_bps = round((row.upper_after - window_start) * 100)
        result.append(
            replace(
                row,
                change_bps=change_bps,
                decision=label_rate_decision(upper_before=window_start, upper_after=row.upper_after),
            )
        )
    return result
