from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class MacroTopic(StrEnum):
    FED_RATE = "fed_rate"
    CPI = "cpi"
    UNEMPLOYMENT = "unemployment"
    GDP = "gdp"


@dataclass(frozen=True)
class MarketCandidate:
    venue: str
    venue_market_id: str
    venue_event_id: str | None
    title: str
    topic: MacroTopic
    closes_at: datetime | None
    outcome_labels: tuple[str, ...]
    outcome_token_ids: tuple[str, ...]
    match_basis: str
    requires_review: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


TOPIC_PATTERNS: tuple[tuple[MacroTopic, re.Pattern[str], str], ...] = (
    (MacroTopic.FED_RATE, re.compile(r"\b(fed|fomc|federal reserve)\b", re.IGNORECASE), "Fed/FOMC"),
    (MacroTopic.CPI, re.compile(r"\b(cpi|consumer price|inflation rate)\b", re.IGNORECASE), "CPI/inflation"),
    (MacroTopic.UNEMPLOYMENT, re.compile(r"\b(unemployment|jobless rate)\b", re.IGNORECASE), "unemployment"),
    (MacroTopic.GDP, re.compile(r"\b(gdp|gross domestic product)\b", re.IGNORECASE), "GDP"),
)
FOREIGN_REGION_PATTERN = re.compile(
    r"\b(china|chinese|eurozone|european union|canada|canadian|uk|united kingdom|"
    r"germany|german|france|french|india|indian|japan|japanese|australia|russia)\b",
    re.IGNORECASE,
)


def classify_macro_title(title: str) -> tuple[MacroTopic, str] | None:
    normalized = " ".join(title.split())
    for topic, pattern, basis in TOPIC_PATTERNS:
        if pattern.search(normalized):
            if topic is not MacroTopic.FED_RATE and FOREIGN_REGION_PATTERN.search(normalized):
                return None
            return topic, basis
    return None


def _timestamp(value: object) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        raise ValueError("market timestamp must be timezone-aware")
    return parsed


def kalshi_candidates(payload: dict[str, Any]) -> list[MarketCandidate]:
    candidates: list[MarketCandidate] = []
    for market in payload.get("markets", []):
        title = str(market.get("title") or market.get("subtitle") or "").strip()
        match = classify_macro_title(title)
        if not match or market.get("status") not in ("open", "active"):
            continue
        topic, basis = match
        candidates.append(
            MarketCandidate(
                venue="kalshi",
                venue_market_id=str(market["ticker"]),
                venue_event_id=str(market.get("event_ticker") or "") or None,
                title=title,
                topic=topic,
                closes_at=_timestamp(market.get("close_time")),
                outcome_labels=("yes", "no"),
                outcome_token_ids=("yes", "no"),
                match_basis=basis,
            )
        )
    return candidates


def polymarket_candidates(payload: dict[str, Any]) -> list[MarketCandidate]:
    markets: list[dict[str, Any]] = list(payload.get("markets", []))
    for event in payload.get("events", []):
        event_title = str(event.get("title") or "")
        for market in event.get("markets", []):
            markets.append({**market, "_event_id": event.get("id"), "_event_title": event_title})

    candidates: list[MarketCandidate] = []
    for market in markets:
        title = str(market.get("question") or market.get("title") or market.get("_event_title") or "").strip()
        classification_text = f'{market.get("_event_title", "")} {title}'.strip()
        match = classify_macro_title(classification_text)
        if not match or market.get("closed") is True or market.get("active") is False:
            continue
        labels = market.get("outcomes") or []
        tokens = market.get("clobTokenIds") or []
        if isinstance(labels, str):
            import json

            labels = json.loads(labels)
        if isinstance(tokens, str):
            import json

            tokens = json.loads(tokens)
        if len(labels) != len(tokens) or len(labels) < 2:
            continue
        topic, basis = match
        candidates.append(
            MarketCandidate(
                venue="polymarket",
                venue_market_id=str(market.get("id") or market.get("conditionId") or ""),
                venue_event_id=str(market.get("_event_id") or "") or None,
                title=title,
                topic=topic,
                closes_at=_timestamp(market.get("endDate") or market.get("end_date_iso")),
                outcome_labels=tuple(str(value) for value in labels),
                outcome_token_ids=tuple(str(value) for value in tokens),
                match_basis=basis,
            )
        )
    return candidates
