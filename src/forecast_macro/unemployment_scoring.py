from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from forecast_macro.models.unemployment import RateBucket, _tenth
from forecast_macro.unemployment_comparison import buckets_from_record


@dataclass(frozen=True)
class ScoredUnemploymentRelease:
    reference_period: str
    release_at: str
    as_of: str
    realized_rate: float
    realized_bucket: str
    model_brier: float  # multi-class Brier: sum over buckets of squared error
    market_brier: float
    model_probability_of_realized: float
    market_probability_of_realized: float


@dataclass(frozen=True)
class UnemploymentScorecard:
    scored_releases: int
    minimum_sample_required: int
    model_brier: float | None
    market_brier: float | None
    model_skill_vs_market: float | None
    sample_gate_passed: bool
    signal_eligible: bool
    signal_eligible_reason: str
    records: list[ScoredUnemploymentRelease]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def final_record_per_release(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    """Last comparison recorded before each release time, keyed by reference period."""
    chosen: dict[str, Mapping[str, Any]] = {}
    for record in records:
        release_at = datetime.fromisoformat(str(record["release_at"]))
        as_of = datetime.fromisoformat(str(record["as_of"]))
        if as_of.tzinfo is None or release_at.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        if as_of >= release_at:
            continue
        period = str(record["reference_period"])
        current = chosen.get(period)
        if current is None or as_of > datetime.fromisoformat(str(current["as_of"])):
            chosen[period] = record
    return chosen


def _bucket_for(rate: float, buckets: Sequence[RateBucket]) -> str:
    for bucket in buckets:
        if bucket.contains(rate):
            return bucket.key
    raise ValueError(f"realized rate {rate} falls outside the bucket set")


def _multiclass_brier(probabilities: Mapping[str, float], realized_key: str) -> float:
    return sum((float(p) - float(key == realized_key)) ** 2 for key, p in probabilities.items())


def score_unemployment_comparisons(
    records: Sequence[Mapping[str, Any]],
    *,
    realized: Mapping[str, float],
    minimum_sample_required: int = 30,
) -> UnemploymentScorecard:
    """Score final pre-release records against the first-published rate for each month.

    `realized` maps reference period (YYYY-MM) to the rate as first published, rounded to a
    tenth. Contracts settle on that figure, so later revisions must not be used.
    """
    scored: list[ScoredUnemploymentRelease] = []
    for period, record in sorted(final_record_per_release(records).items()):
        if period not in realized:
            continue
        rate = _tenth(realized[period])
        buckets = buckets_from_record({"contracts": record["bucket_titles"]})
        key = _bucket_for(rate, buckets)
        scored.append(
            ScoredUnemploymentRelease(
                reference_period=period,
                release_at=str(record["release_at"]),
                as_of=str(record["as_of"]),
                realized_rate=rate,
                realized_bucket=key,
                model_brier=_multiclass_brier(record["model"], key),
                market_brier=_multiclass_brier(record["market"], key),
                model_probability_of_realized=float(record["model"][key]),
                market_probability_of_realized=float(record["market"][key]),
            )
        )
    model = sum(s.model_brier for s in scored) / len(scored) if scored else None
    market = sum(s.market_brier for s in scored) / len(scored) if scored else None
    skill = 1.0 - model / market if model is not None and market else None
    gate = len(scored) >= minimum_sample_required
    return UnemploymentScorecard(
        scored_releases=len(scored),
        minimum_sample_required=minimum_sample_required,
        model_brier=model,
        market_brier=market,
        model_skill_vs_market=skill,
        sample_gate_passed=gate,
        signal_eligible=False,
        signal_eligible_reason=(
            "sample gate not met (D-013 analogue: 30 scored releases)"
            if not gate
            else "eligibility requires a recorded decision even with positive skill (D-007)"
        ),
        records=scored,
    )


def load_unemployment_records(directory: Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("unemployment_comparison_*.json"))
    ]
