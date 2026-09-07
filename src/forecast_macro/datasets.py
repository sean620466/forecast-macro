from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, time
from itertools import pairwise
from pathlib import Path
from zoneinfo import ZoneInfo

from forecast_macro.fomc import RateDecision, label_rate_decision


@dataclass(frozen=True)
class HistoricalFomcRow:
    meeting_at: datetime
    upper_before: float
    upper_after: float
    change_bps: int
    decision: RateDecision
    source: str


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
            calculated_change = round((after - before) * 100)
            if change_bps != calculated_change:
                raise ValueError(f"change_bps mismatch for {meeting_at.date()}")
            if decision is not label_rate_decision(upper_before=before, upper_after=after):
                raise ValueError(f"decision mismatch for {meeting_at.date()}")
            if not raw["source"].startswith("https://www.federalreserve.gov/"):
                raise ValueError("FOMC history requires a Federal Reserve source")
            rows.append(
                HistoricalFomcRow(
                    meeting_at=meeting_at,
                    upper_before=before,
                    upper_after=after,
                    change_bps=change_bps,
                    decision=decision,
                    source=raw["source"],
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
