from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from forecast_macro.datasets import HistoricalFomcRow
from forecast_macro.fomc import RateDecision
from forecast_macro.models.fed import ZLB_UPPER_BOUND


@dataclass(frozen=True)
class ScoredComparison:
    meeting_date: str
    as_of: str
    outcome_cut: int
    heuristic_cut: float
    logistic_cut: float
    market_cut: float
    market_lower: float
    market_upper: float
    policy_rate_upper: float
    non_zlb: bool


@dataclass(frozen=True)
class ComparisonScorecard:
    scored_meetings: int
    non_zlb_meetings: int
    minimum_sample_required: int
    heuristic_brier: float | None
    logistic_brier: float | None
    market_brier: float | None
    heuristic_skill_vs_market: float | None
    logistic_skill_vs_market: float | None
    sample_gate_passed: bool
    # D-007: only a positive out-of-sample skill against the market on the required sample
    # can make signal eligibility reviewable. Even then it is a review, not a switch.
    signal_eligible: bool
    signal_eligible_reason: str
    records: list[ScoredComparison]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _brier(pairs: Sequence[tuple[float, int]]) -> float | None:
    if not pairs:
        return None
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def _skill(model: float | None, baseline: float | None) -> float | None:
    if model is None or baseline is None or baseline <= 0:
        return None
    return 1.0 - model / baseline


def final_record_per_meeting(
    records: Sequence[Mapping[str, Any]], *, meetings: Sequence[HistoricalFomcRow]
) -> dict[str, Mapping[str, Any]]:
    """Keep the last comparison recorded before each meeting's decision time.

    Records made after the decision, or for meetings that have not happened, are excluded.
    Only records with a market probability can be scored against the market.
    """
    decision_at = {row.meeting_at.date().isoformat(): row.meeting_at for row in meetings}
    chosen: dict[str, Mapping[str, Any]] = {}
    for record in records:
        meeting_date = str(record.get("meeting_date", ""))
        if meeting_date not in decision_at or not record.get("market"):
            continue
        as_of = datetime.fromisoformat(str(record["as_of"]))
        if as_of.tzinfo is None:
            raise ValueError("comparison as_of must be timezone-aware")
        if as_of >= decision_at[meeting_date]:
            continue
        current = chosen.get(meeting_date)
        if current is None or as_of > datetime.fromisoformat(str(current["as_of"])):
            chosen[meeting_date] = record
    return chosen


def score_comparisons(
    records: Sequence[Mapping[str, Any]],
    *,
    meetings: Sequence[HistoricalFomcRow],
    minimum_sample_required: int = 30,
) -> ComparisonScorecard:
    outcomes = {row.meeting_at.date().isoformat(): row for row in meetings}
    scored: list[ScoredComparison] = []
    for meeting_date, record in sorted(final_record_per_meeting(records, meetings=meetings).items()):
        row = outcomes[meeting_date]
        market = record["market"]
        policy_rate = float(record["features"]["policy_rate_upper"])
        scored.append(
            ScoredComparison(
                meeting_date=meeting_date,
                as_of=str(record["as_of"]),
                outcome_cut=int(row.decision is RateDecision.CUT),
                heuristic_cut=float(record["heuristic_cut"]),
                logistic_cut=float(record["logistic_cut"]),
                market_cut=float(market["probability"]),
                market_lower=float(market["lower_bound"]),
                market_upper=float(market["upper_bound"]),
                policy_rate_upper=policy_rate,
                non_zlb=policy_rate > ZLB_UPPER_BOUND,
            )
        )
    heuristic = _brier([(s.heuristic_cut, s.outcome_cut) for s in scored])
    logistic = _brier([(s.logistic_cut, s.outcome_cut) for s in scored])
    market = _brier([(s.market_cut, s.outcome_cut) for s in scored])
    non_zlb = sum(s.non_zlb for s in scored)
    gate = non_zlb >= minimum_sample_required
    logistic_skill = _skill(logistic, market)
    return ComparisonScorecard(
        scored_meetings=len(scored),
        non_zlb_meetings=non_zlb,
        minimum_sample_required=minimum_sample_required,
        heuristic_brier=heuristic,
        logistic_brier=logistic,
        market_brier=market,
        heuristic_skill_vs_market=_skill(heuristic, market),
        logistic_skill_vs_market=logistic_skill,
        sample_gate_passed=gate,
        signal_eligible=False,
        signal_eligible_reason=(
            "sample gate not met (D-013)"
            if not gate
            else "positive skill vs market; eligibility requires a recorded decision (D-007)"
            if logistic_skill is not None and logistic_skill > 0
            else "no positive skill vs market (D-007)"
        ),
        records=scored,
    )


def load_comparison_records(directory: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("fed_comparison_*.json")):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    return records


def today_utc() -> date:
    return datetime.now(UTC).date()
