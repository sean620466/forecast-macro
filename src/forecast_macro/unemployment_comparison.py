from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from forecast_macro.fees import schedule_for
from forecast_macro.market_review import _bucket, ladder_step_for
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
    """One-month-ahead bucket comparison; also used for Core CPI YoY (topic field says which)."""

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
    # D-003 net of fees: model probability minus the break-even probability at the market ask.
    net_edge_after_fees: dict[str, float] | None
    fee_schedule_id: str | None
    market_observed_at: str
    market_source_file: str
    bucket_titles: dict[str, str]
    signal_eligible: bool = False
    signal_eligible_reason: str = "no out-of-sample skill against market prices (D-007)"
    topic: str = "unemployment"
    contract_series: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def next_release(
    schedule: Sequence[ScheduledRelease], *, as_of: datetime, series: str
) -> ScheduledRelease:
    upcoming = sorted(
        (row for row in schedule if row.series == series and row.release_at > as_of),
        key=lambda row: row.release_at,
    )
    if not upcoming:
        raise ValueError(f"no scheduled {series} release after as_of")
    return upcoming[0]


def next_employment_release(
    schedule: Sequence[ScheduledRelease], *, as_of: datetime
) -> ScheduledRelease:
    return next_release(schedule, as_of=as_of, series="employment_situation")


def is_ladder_keys(keys: Sequence[str]) -> bool:
    """Exclusive-bucket keys derived from a threshold ladder: le_X, X..., gt_X (contracts.py)."""
    return any(str(k).startswith("le_") for k in keys) and any(str(k).startswith("gt_") for k in keys)


def ladder_buckets(keys: Sequence[str], *, step: float) -> list[RateBucket]:
    """Bucket definitions for ladder keys.

    A Kalshi rung "above F" pays when the published rate exceeds F; on a tenth-point grid
    that is rate >= F + step. So `le_F` is the lower tail (<= F), a plain key `V` is the
    exact published value V, and `gt_F` is the upper tail (>= F + step).
    """
    buckets: list[RateBucket] = []
    for key in keys:
        text = str(key)
        if text.startswith("le_"):
            buckets.append(RateBucket(key=text, kind="lower", value=_tenth_value(float(text[3:]))))
        elif text.startswith("gt_"):
            buckets.append(RateBucket(key=text, kind="upper", value=_tenth_value(float(text[3:]) + step)))
        else:
            buckets.append(RateBucket(key=text, kind="exact", value=_tenth_value(float(text))))
    return buckets


def _tenth_value(value: float) -> float:
    return round(value, 1)


def ladder_bucket_titles(keys: Sequence[str], *, step: float, subject: str) -> dict[str, str]:
    """Human titles for ladder buckets in the same "will be ≤X%" form as Polymarket titles."""
    titles: dict[str, str] = {}
    for bucket in ladder_buckets(keys, step=step):
        if bucket.kind == "lower":
            titles[bucket.key] = f"{subject} will be ≤{bucket.value:.1f}%"
        elif bucket.kind == "upper":
            titles[bucket.key] = f"{subject} will be ≥{bucket.value:.1f}%"
        else:
            titles[bucket.key] = f"{subject} will be {bucket.value:.1f}%"
    return titles


def buckets_from_record(record: Mapping[str, Any]) -> list[RateBucket]:
    """Bucket definitions from a priced record.

    Polymarket events: one YES/NO contract per bucket, parsed from the contract titles and
    keyed by market id. Kalshi ladders: keys of the derived exclusive buckets (`probabilities`
    when present, otherwise the `contracts` mapping of a comparison record, whose keys are the
    same bucket keys).
    """
    keys = list((record.get("probabilities") or record.get("contracts") or {}).keys())
    if is_ladder_keys(keys):
        return ladder_buckets(keys, step=ladder_step_for(str(record.get("topic", "unemployment"))))
    buckets: list[RateBucket] = []
    for market_id, title in record.get("contracts", {}).items():
        parsed = _bucket(str(title))
        if parsed is None or parsed[0].endswith("_strict"):
            raise ValueError(f"cannot read a rounded bucket from title {title!r}")
        kind, value = parsed
        buckets.append(RateBucket(key=str(market_id), kind=kind, value=value))
    return buckets


def latest_bucket_record(
    snapshot_dir: Path,
    *,
    release_at: datetime,
    topic: str,
    venue: str = "polymarket",
    contract_series: str | None = None,
) -> tuple[Mapping[str, Any], str] | None:
    """Newest priced record of `topic` on `venue` that settles on the given release.

    `contract_series` (e.g. core_cpi_yoy_nsa) filters records that carry the series the
    verified rules identified; records without the field are accepted only when no series
    filter is given (pre-task-40 Polymarket snapshots).
    """
    for path in sorted(snapshot_dir.glob("market_prices_*.json"), reverse=True):
        for record in json.loads(path.read_text(encoding="utf-8")):
            if (
                record.get("venue") == venue
                and record.get("topic") == topic
                and record.get("probabilities")
                and record.get("outcome_at")
                and datetime.fromisoformat(str(record["outcome_at"])) == release_at
                and (contract_series is None or record.get("contract_series") == contract_series)
            ):
                return record, path.name
    return None


def latest_unemployment_record(
    snapshot_dir: Path, *, release_at: datetime
) -> tuple[Mapping[str, Any], str] | None:
    return latest_bucket_record(snapshot_dir, release_at=release_at, topic="unemployment")


def build_unemployment_comparison(
    *,
    as_of: datetime,
    release: ScheduledRelease,
    history: Sequence[MonthlyRate],
    history_vintage: str,
    record: Mapping[str, Any],
    source_file: str,
    model_version: str = MODEL_VERSION,
    topic: str = "unemployment",
    change_distribution: Mapping[float, float] | None = None,
) -> UnemploymentComparisonRecord:
    """`change_distribution` replaces the empirical one-month-change draw (keyed by change from
    the latest rate, in tenths); the base-effect CPI model supplies it (task 41)."""
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    rows = sorted(history, key=lambda r: r.month)
    latest = rows[-1]
    distribution = dict(change_distribution) if change_distribution is not None else monthly_change_distribution(rows)
    buckets = buckets_from_record(record)
    keys = list(record["probabilities"].keys())
    if is_ladder_keys(keys):
        step = ladder_step_for(str(record.get("topic", topic)))
        titles = ladder_bucket_titles(keys, step=step, subject=f"{record.get('venue_event_id', '')} ladder bucket")
    else:
        titles = {str(k): str(v) for k, v in record.get("contracts", {}).items()}
    model = {p.outcome: p.probability for p in next_month_bucket_probabilities(latest.value, distribution, buckets)}
    market = {key: float(value) for key, value in record["probabilities"].items()}
    bounds = {key: [float(lo), float(hi)] for key, (lo, hi) in record.get("probability_bounds", {}).items()}
    if set(market) != set(model):
        raise ValueError("market and model bucket sets differ")
    quotes = record.get("quotes") or {}
    fee_ids = {str((quotes.get(k) or {}).get("fees", {}).get("fee_schedule_id", "")) for k in model}
    fee_id = next(iter(fee_ids)) if len(fee_ids) == 1 and next(iter(fee_ids)) else None
    schedule = schedule_for(fee_id) if fee_id else None
    net_edge = (
        {k: schedule.net_edge(model[k], float(quotes[k]["ask"])) for k in model if k in quotes}
        if schedule is not None and all(k in quotes for k in model)
        else None
    )
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
        model_version=model_version,
        model=model,
        market=market,
        market_bounds=bounds,
        edge={key: model[key] - market[key] for key in model},
        net_edge_after_fees=net_edge,
        fee_schedule_id=fee_id,
        market_observed_at=str(record.get("observed_at", "")),
        market_source_file=source_file,
        bucket_titles=titles,
        topic=topic,
        contract_series=record.get("contract_series"),
    )
