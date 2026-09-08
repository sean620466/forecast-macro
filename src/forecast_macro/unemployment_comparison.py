from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from forecast_macro.market_review import _bucket
from forecast_macro.models.unemployment import (
    MODEL_VERSION,
    MonthlyRate,
    RateBucket,
    monthly_change_distribution,
    next_month_bucket_probabilities,
)
from forecast_macro.release_schedule import ScheduledRelease


@dataclass(frozen=True)
class UnemploymentComparisonRecord:
    as_of: str
    release_at: str
    reference_period: str
    venue: str
    venue_event_id: str
    latest_rate: float
    latest_month: str
    history_start: str
    history_vintage: str
    change_distribution: dict[str, float]
    model_version: str
    model: dict[str, float]  # bucket key -> probability
    market: dict[str, float]
    market_bounds: dict[str, list[float]]
    edge: dict[str, float]
    market_observed_at: str
    market_source_file: str
    bucket_titles: dict[str, str]
    signal_eligible: bool = False
    signal_eligible_reason: str = "no out-of-sample skill against market prices (D-007)"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def next_employment_release(
    schedule: Sequence[ScheduledRelease], *, as_of: datetime
) -> ScheduledRelease:
    upcoming = sorted(
        (row for row in schedule if row.series == "employment_situation" and row.release_at > as_of),
        key=lambda row: row.release_at,
    )
    if not upcoming:
        raise ValueError("no scheduled Employment Situation release after as_of")
    return upcoming[0]


def buckets_from_record(record: Mapping[str, Any]) -> list[RateBucket]:
    """Bucket definitions from the priced record's contract titles, keyed by market id."""
    buckets: list[RateBucket] = []
    for market_id, title in record.get("contracts", {}).items():
        parsed = _bucket(str(title))
        if parsed is None or parsed[0].endswith("_strict"):
            raise ValueError(f"cannot read a rounded bucket from title {title!r}")
        kind, value = parsed
        buckets.append(RateBucket(key=str(market_id), kind=kind, value=value))
    return buckets


def latest_unemployment_record(
    snapshot_dir: Path, *, release_at: datetime
) -> tuple[Mapping[str, Any], str] | None:
    """Newest priced Polymarket unemployment record that settles on the given release."""
    for path in sorted(snapshot_dir.glob("market_prices_*.json"), reverse=True):
        for record in json.loads(path.read_text(encoding="utf-8")):
            if (
                record.get("venue") == "polymarket"
                and record.get("topic") == "unemployment"
                and record.get("probabilities")
                and record.get("outcome_at")
                and datetime.fromisoformat(str(record["outcome_at"])) == release_at
            ):
                return record, path.name
    return None


def build_unemployment_comparison(
    *,
    as_of: datetime,
    release: ScheduledRelease,
    history: Sequence[MonthlyRate],
    history_vintage: str,
    record: Mapping[str, Any],
    source_file: str,
) -> UnemploymentComparisonRecord:
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    rows = sorted(history, key=lambda r: r.month)
    latest = rows[-1]
    distribution = monthly_change_distribution(rows)
    buckets = buckets_from_record(record)
    model = {p.outcome: p.probability for p in next_month_bucket_probabilities(latest.value, distribution, buckets)}
    market = {key: float(value) for key, value in record["probabilities"].items()}
    bounds = {key: [float(lo), float(hi)] for key, (lo, hi) in record.get("probability_bounds", {}).items()}
    if set(market) != set(model):
        raise ValueError("market and model bucket sets differ")
    return UnemploymentComparisonRecord(
        as_of=as_of.astimezone(UTC).isoformat(),
        release_at=release.release_at.isoformat(),
        reference_period=release.reference_period,
        venue=str(record["venue"]),
        venue_event_id=str(record["venue_event_id"]),
        latest_rate=latest.value,
        latest_month=latest.month.isoformat(),
        history_start=rows[0].month.isoformat(),
        history_vintage=history_vintage,
        change_distribution={f"{change:+.1f}": probability for change, probability in distribution.items()},
        model_version=MODEL_VERSION,
        model=model,
        market=market,
        market_bounds=bounds,
        edge={key: model[key] - market[key] for key in model},
        market_observed_at=str(record.get("observed_at", "")),
        market_source_file=source_file,
        bucket_titles={str(k): str(v) for k, v in record.get("contracts", {}).items()},
    )
