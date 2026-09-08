from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Mapping, Sequence


class ReviewStatus(StrEnum):
    REJECTED = "rejected"
    RULES_REQUIRED = "structure_valid_rules_required"
    APPROVED = "approved"


@dataclass(frozen=True)
class ContractRuleMetadata:
    resolution_source: str
    rules_text_hash: str
    rules_version: str


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
_LOWER = re.compile(rf"(?:{_NUMBER}%\s+or less|[≤<]\s*{_NUMBER}%)", re.IGNORECASE)
_UPPER = re.compile(rf"(?:{_NUMBER}%\s+or more|[≥>]\s*{_NUMBER}%)", re.IGNORECASE)


def _extract_value(match: re.Match[str]) -> float:
    values = [value for value in match.groups() if value is not None]
    return float(values[0])


def _bucket(title: str) -> tuple[str, float] | None:
    for kind, pattern in (("lower", _LOWER), ("upper", _UPPER), ("exact", _EXACT)):
        match = pattern.search(title)
        if match:
            return kind, _extract_value(match)
    return None


def _validate_group(rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    blockers: list[str] = []
    buckets = [_bucket(str(row.get("title", ""))) for row in rows]
    if any(bucket is None for bucket in buckets):
        return ("unrecognized bucket title",)

    parsed = [bucket for bucket in buckets if bucket is not None]
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
            if rules is None or not all(
                (rules.resolution_source.strip(), rules.rules_text_hash.strip(), rules.rules_version.strip())
            ):
                blockers.append("verified resolution source and versioned rules required")
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
