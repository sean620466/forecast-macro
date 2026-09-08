from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from forecast_macro.datasets import HistoricalFomcRow
from forecast_macro.fed_model_comparison import (
    _features,
    fit_hike_given_no_cut,
    hike_probability_given_no_cut,
)
from forecast_macro.fomc import RateDecision
from forecast_macro.models.fed import (
    apply_cut_feasibility,
    rate_decision_probabilities,
    split_remainder,
)
from forecast_macro.models.logistic import fit_logistic
from forecast_macro.release_schedule import ScheduledRelease
from forecast_macro.snapshots import HistoricalFeatureSnapshot

MODEL_VERSION = "fed-live-0.2-three-way-uncalibrated"
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
    # D-016: full three-way view with bounds; `probability` above is the cut component.
    hold_lower_bound: float = 0.0
    hold_upper_bound: float = 0.0
    hike_lower_bound: float = 0.0
    hike_upper_bound: float = 0.0
    # D-018: the priced ladder was wider than 0.35 (far-dated, thin tails).
    low_liquidity: bool = False


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
    # D-016 three-way probabilities (cut/hold/hike) and per-outcome edges vs the market.
    heuristic_three_way: dict[str, float] | None = None
    logistic_three_way: dict[str, float] | None = None
    heuristic_three_way_edge: dict[str, float] | None = None
    logistic_three_way_edge: dict[str, float] | None = None
    # D-017: a CPI or Employment Situation release at 08:30 ET on the meeting day gives the
    # market information the D-1 model input lacks; such meetings are scored separately.
    same_day_release: bool = False
    same_day_release_series: list[str] | None = None
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
    totals = {"cut": 0.0, "hold": 0.0, "hike": 0.0}
    lowers = {"cut": 0.0, "hold": 0.0, "hike": 0.0}
    uppers = {"cut": 0.0, "hold": 0.0, "hike": 0.0}
    for key, value in probabilities.items():
        kind, rate = _bucket_rate(key)
        lo, hi = bounds.get(key, (value, value))
        if kind != "gt" and rate < current_upper:
            outcome = "cut"
        elif kind == "eq" and abs(rate - current_upper) < 1e-9:
            outcome = "hold"
        else:
            outcome = "hike"
        totals[outcome] += value
        lowers[outcome] += lo
        uppers[outcome] += hi
    completeness = record.get("completeness") or {}
    return MarketCutProbability(
        low_liquidity=bool(completeness.get("low_liquidity", 0.0)),
        probability=totals["cut"],
        lower_bound=min(lowers["cut"], 1.0),
        upper_bound=min(uppers["cut"], 1.0),
        hold_probability=totals["hold"],
        hike_probability=totals["hike"],
        current_upper=current_upper,
        observed_at=str(record.get("observed_at", "")),
        source_file=source_file,
        hold_lower_bound=min(lowers["hold"], 1.0),
        hold_upper_bound=min(uppers["hold"], 1.0),
        hike_lower_bound=min(lowers["hike"], 1.0),
        hike_upper_bound=min(uppers["hike"], 1.0),
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


def model_three_way_probabilities(
    snapshot: HistoricalFeatureSnapshot,
    training: Sequence[HistoricalFomcRow],
    training_snapshots: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, float], dict[str, float]]:
    """Heuristic baseline and logistic candidate as cut/hold/hike vectors (D-016)."""
    heuristic = {
        item.outcome: item.probability
        for item in rate_decision_probabilities(
            inflation_yoy=snapshot.cpi_yoy_nsa,
            unemployment_rate=snapshot.unemployment_rate,
            unemployment_change_3m=snapshot.unemployment_change_3m,
            policy_rate=snapshot.policy_rate_upper,
        )
    }
    by_date = {str(row["meeting_date"]): row for row in training_snapshots}
    rows = list(training)
    cut_model = fit_logistic(
        [_features(by_date[row.meeting_at.date().isoformat()]) for row in rows],
        [int(row.decision is RateDecision.CUT) for row in rows],
    )
    hike_model = fit_hike_given_no_cut(rows, [dict(item) for item in training_snapshots])
    features = _features(snapshot.to_dict())
    cut = apply_cut_feasibility(cut_model.predict(features), policy_rate=snapshot.policy_rate_upper)
    cut, hold, hike = split_remainder(cut, hike_probability_given_no_cut(hike_model, features))
    return heuristic, {"cut": cut, "hold": hold, "hike": hike}


def model_cut_probabilities(
    snapshot: HistoricalFeatureSnapshot, training: Sequence[HistoricalFomcRow],
    training_snapshots: Sequence[Mapping[str, Any]],
) -> tuple[float, float]:
    """Cut components of the three-way models (kept for older callers)."""
    heuristic, logistic = model_three_way_probabilities(snapshot, training, training_snapshots)
    return heuristic["cut"], logistic["cut"]


def _market_three_way(market: MarketCutProbability) -> dict[str, float]:
    return {
        "cut": market.probability,
        "hold": market.hold_probability,
        "hike": market.hike_probability,
    }


def same_day_releases(
    schedule: Sequence[ScheduledRelease], *, meeting_date: date
) -> list[str]:
    """Data releases (CPI, Employment Situation) published on the meeting day itself."""
    return sorted(
        {
            row.series
            for row in schedule
            if row.series in ("cpi", "employment_situation") and row.release_at.date() == meeting_date
        }
    )


def build_comparison(
    *,
    as_of: datetime,
    meeting: ScheduledRelease,
    snapshot: HistoricalFeatureSnapshot,
    heuristic_cut: float,
    logistic_cut: float,
    training_size: int,
    market: MarketCutProbability | None,
    heuristic_three_way: Mapping[str, float] | None = None,
    logistic_three_way: Mapping[str, float] | None = None,
    schedule: Sequence[ScheduledRelease] | None = None,
) -> FedComparisonRecord:
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    meeting_date = meeting.release_at.date()
    releases = same_day_releases(schedule, meeting_date=meeting_date) if schedule else []
    market_vector = _market_three_way(market) if market else None

    def edges(vector: Mapping[str, float] | None) -> dict[str, float] | None:
        if vector is None or market_vector is None:
            return None
        return {key: vector[key] - market_vector[key] for key in ("cut", "hold", "hike")}

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
        heuristic_three_way=dict(heuristic_three_way) if heuristic_three_way else None,
        logistic_three_way=dict(logistic_three_way) if logistic_three_way else None,
        heuristic_three_way_edge=edges(heuristic_three_way),
        logistic_three_way_edge=edges(logistic_three_way),
        same_day_release=bool(releases),
        same_day_release_series=releases or None,
    )
