from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from forecast_macro.datasets import HistoricalFomcRow
from forecast_macro.fed_model_comparison import _features
from forecast_macro.fomc import RateDecision
from forecast_macro.models.fed import apply_cut_feasibility, rate_cut_probability
from forecast_macro.models.logistic import fit_logistic
from forecast_macro.release_schedule import ScheduledRelease
from forecast_macro.snapshots import HistoricalFeatureSnapshot

MODEL_VERSION = "fed-live-0.1-uncalibrated"
_MONTH_CODES = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


@dataclass(frozen=True)
class MarketCutProbability:
    probability: float
    lower_bound: float
    upper_bound: float
    hold_probability: float
    hike_probability: float
    current_upper: float
    observed_at: str
    source_file: str


@dataclass(frozen=True)
class FedComparisonRecord:
    as_of: str
    meeting_date: str
    event_ticker: str
    features: dict[str, object]
    model_version: str
    heuristic_cut: float
    logistic_cut: float
    logistic_training_meetings: int
    market: dict[str, object] | None
    heuristic_edge: float | None
    logistic_edge: float | None
    # D-007/D-012: comparisons are recorded for a future skill evaluation, never shown as signals.
    signal_eligible: bool = False
    signal_eligible_reason: str = "no out-of-sample Brier skill against market prices yet (D-007)"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def next_scheduled_meeting(schedule: Sequence[ScheduledRelease], *, as_of: datetime) -> ScheduledRelease:
    upcoming = sorted(
        (row for row in schedule if row.series == "fomc" and row.release_at > as_of),
        key=lambda row: row.release_at,
    )
    if not upcoming:
        raise ValueError("no scheduled FOMC decision after as_of in the release calendar")
    return upcoming[0]


def kalshi_event_ticker(meeting_date: date) -> str:
    return f"KXFED-{meeting_date.year % 100:02d}{_MONTH_CODES[meeting_date.month - 1]}"


def _bucket_rate(key: str) -> tuple[str, float]:
    if key.startswith("le_"):
        return "le", float(key[3:])
    if key.startswith("gt_"):
        return "gt", float(key[3:])
    return "eq", float(key)


def market_cut_probability(
    record: Mapping[str, Any], *, current_upper: float, source_file: str
) -> MarketCutProbability:
    """Collapse a priced ladder record into P(cut) = P(upper bound after meeting < current)."""
    probabilities = record.get("probabilities") or {}
    bounds = record.get("probability_bounds") or {}
    if not probabilities:
        raise ValueError("price record has no probabilities")
    cut = hold = hike = 0.0
    lower = upper = 0.0
    for key, value in probabilities.items():
        kind, rate = _bucket_rate(key)
        lo, hi = bounds.get(key, (value, value))
        if kind == "le":
            below = rate < current_upper
        elif kind == "gt":
            below = False
        else:
            below = rate < current_upper
        if below:
            cut += value
            lower += lo
            upper += hi
        elif kind == "eq" and abs(rate - current_upper) < 1e-9:
            hold += value
        else:
            hike += value
    return MarketCutProbability(
        probability=cut,
        lower_bound=min(lower, 1.0),
        upper_bound=min(upper, 1.0),
        hold_probability=hold,
        hike_probability=hike,
        current_upper=current_upper,
        observed_at=str(record.get("observed_at", "")),
        source_file=source_file,
    )


def latest_ladder_record(
    snapshot_dir: Path, *, event_ticker: str
) -> tuple[Mapping[str, Any], str] | None:
    """Newest priced record for the event across the committed snapshot files."""
    for path in sorted(snapshot_dir.glob("market_prices_*.json"), reverse=True):
        for record in json.loads(path.read_text(encoding="utf-8")):
            if (
                record.get("venue") == "kalshi"
                and record.get("venue_event_id") == event_ticker
                and record.get("probabilities")
            ):
                return record, path.name
    return None


def model_cut_probabilities(
    snapshot: HistoricalFeatureSnapshot, training: Sequence[HistoricalFomcRow],
    training_snapshots: Sequence[Mapping[str, Any]],
) -> tuple[float, float]:
    """Heuristic baseline and the logistic candidate refitted on all available history."""
    heuristic = next(
        item.probability
        for item in rate_cut_probability(
            inflation_yoy=snapshot.cpi_yoy_nsa,
            unemployment_rate=snapshot.unemployment_rate,
            unemployment_change_3m=snapshot.unemployment_change_3m,
            policy_rate=snapshot.policy_rate_upper,
        )
        if item.outcome == "cut"
    )
    by_date = {str(row["meeting_date"]): row for row in training_snapshots}
    model = fit_logistic(
        [_features(by_date[row.meeting_at.date().isoformat()]) for row in training],
        [int(row.decision is RateDecision.CUT) for row in training],
    )
    logistic = apply_cut_feasibility(
        model.predict(_features(snapshot.to_dict())), policy_rate=snapshot.policy_rate_upper
    )
    return heuristic, logistic


def build_comparison(
    *,
    as_of: datetime,
    meeting: ScheduledRelease,
    snapshot: HistoricalFeatureSnapshot,
    heuristic_cut: float,
    logistic_cut: float,
    training_size: int,
    market: MarketCutProbability | None,
) -> FedComparisonRecord:
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    meeting_date = meeting.release_at.date()
    return FedComparisonRecord(
        as_of=as_of.astimezone(UTC).isoformat(),
        meeting_date=meeting_date.isoformat(),
        event_ticker=kalshi_event_ticker(meeting_date),
        features=snapshot.to_dict(),
        model_version=MODEL_VERSION,
        heuristic_cut=heuristic_cut,
        logistic_cut=logistic_cut,
        logistic_training_meetings=training_size,
        market=asdict(market) if market else None,
        heuristic_edge=(heuristic_cut - market.probability) if market else None,
        logistic_edge=(logistic_cut - market.probability) if market else None,
    )
