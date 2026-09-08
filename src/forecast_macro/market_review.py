from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from itertools import pairwise
from typing import Any

from forecast_macro.official_sources import is_official_source


class ReviewStatus(StrEnum):
    REJECTED = "rejected"
    RULES_REQUIRED = "structure_valid_rules_required"
    APPROVED = "approved"


@dataclass(frozen=True)
class ContractRuleMetadata:
    resolution_source: str
    rules_text_hash: str
    rules_version: str
    series_id: str = ""
    resolution_source_origin: str = ""  # "field" | "description"
    fetched_at: str = ""


@dataclass(frozen=True)
class CandidateReview:
    venue: str
    venue_event_id: str | None
    venue_market_id: str
    topic: str
    status: ReviewStatus
    checks_passed: tuple[str, ...]
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_NUMBER = r"(\d+(?:\.\d+)?)"
_EXACT = re.compile(rf"\bbe\s+{_NUMBER}%", re.IGNORECASE)
# Inclusive tails ("or less", "≤") are the only forms that line up with 0.1-point buckets.
_LOWER = re.compile(rf"(?:{_NUMBER}%\s+or (?:less|lower|below)|≤\s*{_NUMBER}%)", re.IGNORECASE)
_UPPER = re.compile(rf"(?:{_NUMBER}%\s+or (?:more|higher|above)|≥\s*{_NUMBER}%)", re.IGNORECASE)
# Strict tails ("<", ">", "below", "above") exclude the boundary value; they are reported,
# never silently treated as inclusive (R6-M2).
_LOWER_STRICT = re.compile(rf"(?:<\s*{_NUMBER}%|\bbelow\s+{_NUMBER}%|\bunder\s+{_NUMBER}%)", re.IGNORECASE)
_UPPER_STRICT = re.compile(rf"(?:>\s*{_NUMBER}%|\babove\s+{_NUMBER}%|\bover\s+{_NUMBER}%)", re.IGNORECASE)
_SUBJECT_NOISE = re.compile(
    rf"({_NUMBER}%\s+or (?:less|lower|below|more|higher|above)|[≤≥<>]\s*{_NUMBER}%|"
    rf"\b(?:below|under|above|over)\s+{_NUMBER}%|{_NUMBER}%)",
    re.IGNORECASE,
)


def _extract_value(match: re.Match[str]) -> float:
    values = [value for value in match.groups() if value is not None]
    return float(values[0])


def _bucket(title: str) -> tuple[str, float] | None:
    patterns = (
        ("lower", _LOWER),
        ("upper", _UPPER),
        ("lower_strict", _LOWER_STRICT),
        ("upper_strict", _UPPER_STRICT),
        ("exact", _EXACT),
    )
    for kind, pattern in patterns:
        match = pattern.search(title)
        if match:
            return kind, _extract_value(match)
    return None


def _subject(title: str) -> str:
    """The title with its bucket removed; every market in one event must share it."""
    stripped = _SUBJECT_NOISE.sub(" ", title)
    return " ".join(stripped.lower().replace("?", "").split())


LADDER_STEP = 0.25


def is_threshold_ladder(rows: Sequence[Mapping[str, Any]]) -> bool:
    return len(rows) >= 2 and all(
        row.get("strike") is not None and row.get("strike_type") == "greater" for row in rows
    )


def _validate_ladder(rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """A cumulative ladder is complete when its floors form one contiguous fixed-step grid."""
    blockers: list[str] = []
    floors = sorted(float(row["strike"]) for row in rows)
    if len(set(floors)) != len(floors):
        blockers.append("duplicate ladder rung")
    if any(abs((b - a) - LADDER_STEP) > 1e-9 for a, b in pairwise(floors)):
        blockers.append(f"ladder rungs are not contiguous in {LADDER_STEP} steps")
    if len({_subject(str(row.get("title", ""))) for row in rows}) != 1:
        blockers.append("ladder mixes reference meetings or series")
    return tuple(blockers)


def _validate_group(rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    if is_threshold_ladder(rows):
        return _validate_ladder(rows)
    blockers: list[str] = []
    titles = [str(row.get("title", "")) for row in rows]
    buckets = [_bucket(title) for title in titles]
    if any(bucket is None for bucket in buckets):
        return ("unrecognized bucket title",)

    parsed = [bucket for bucket in buckets if bucket is not None]
    if any(kind.endswith("_strict") for kind, _ in parsed):
        blockers.append("strict inequality tail cannot be reconciled with 0.1-point buckets")
    if len({_subject(title) for title in titles}) != 1:
        blockers.append("bucket set mixes reference periods or series")
    lower = sorted(value for kind, value in parsed if kind == "lower")
    upper = sorted(value for kind, value in parsed if kind == "upper")
    exact = sorted(value for kind, value in parsed if kind == "exact")
    if len(lower) != 1 or len(upper) != 1:
        blockers.append("bucket set must have one lower tail and one upper tail")
    if len(set(parsed)) != len(parsed):
        blockers.append("duplicate bucket")
    if lower and upper:
        expected = [round(lower[0] + step / 10, 1) for step in range(1, round((upper[0] - lower[0]) * 10))]
        if exact != expected:
            blockers.append("bucket set is not contiguous in 0.1 percentage-point steps")
    return tuple(blockers)


def review_market_candidates(
    rows: Sequence[Mapping[str, Any]],
    *,
    rule_metadata: Mapping[str, ContractRuleMetadata] | None = None,
) -> list[CandidateReview]:
    """Review candidate structure and keep approval locked until rule evidence exists."""
    metadata = rule_metadata or {}
    groups: dict[tuple[str, str | None, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (str(row.get("venue", "")), row.get("venue_event_id"), str(row.get("topic", "")))
        groups[key].append(row)

    reviews: list[CandidateReview] = []
    for group_rows in groups.values():
        group_blockers = _validate_group(group_rows)
        for row in group_rows:
            blockers = list(group_blockers)
            checks = ["macro topic classified", "candidate requires manual review"]
            labels = tuple(str(value).lower() for value in row.get("outcome_labels", ()))
            tokens = tuple(str(value) for value in row.get("outcome_token_ids", ()))
            if labels != ("yes", "no") or len(tokens) != 2 or not all(tokens):
                blockers.append("invalid YES/NO token mapping")
            else:
                checks.append("YES/NO token mapping complete")

            market_id = str(row.get("venue_market_id", ""))
            if not row.get("close_time_verified", False):
                blockers.append("contract close time requires rule-based timezone verification")
            rules = metadata.get(market_id)
            topic = str(row.get("topic", ""))
            if rules is None or not all(
                (rules.resolution_source.strip(), rules.rules_text_hash.strip(), rules.rules_version.strip())
            ):
                blockers.append("verified resolution source and versioned rules required")
            elif not is_official_source(rules.resolution_source, topic=topic):
                # Metadata is only trusted when its source passes the shared official-host test,
                # so a caller cannot approve a contract with an arbitrary string (R6-H2).
                blockers.append("resolution source is not the required official agency")
            else:
                checks.append("resolution source and versioned rules verified")

            if group_blockers:
                status = ReviewStatus.REJECTED
            elif blockers:
                status = ReviewStatus.RULES_REQUIRED
                checks.append("bucket structure complete")
            else:
                status = ReviewStatus.APPROVED
                checks.append("bucket structure complete")

            reviews.append(
                CandidateReview(
                    venue=str(row.get("venue", "")),
                    venue_event_id=str(row.get("venue_event_id")) if row.get("venue_event_id") else None,
                    venue_market_id=market_id,
                    topic=str(row.get("topic", "")),
                    status=status,
                    checks_passed=tuple(checks),
                    blockers=tuple(blockers),
                )
            )
    return reviews
