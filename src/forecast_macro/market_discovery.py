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
    close_time_verified: bool = False
    # Venue-reported close, kept verbatim for reconciliation against the official calendar.
    venue_close_raw: str | None = None
    # Threshold contracts (Kalshi "greater than F"): the floor and its comparison type.
    strike: float | None = None
    strike_type: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


TOPIC_PATTERNS: tuple[tuple[MacroTopic, re.Pattern[str], str], ...] = (
    (MacroTopic.FED_RATE, re.compile(r"\b(fed|fomc|federal reserve|federal funds|fed funds)\b", re.IGNORECASE), "Fed/FOMC"),
    (MacroTopic.CPI, re.compile(r"\b(cpi|consumer price|inflation rate)\b", re.IGNORECASE), "CPI/inflation"),
    (MacroTopic.UNEMPLOYMENT, re.compile(r"\b(unemployment|jobless rate)\b", re.IGNORECASE), "unemployment"),
    (MacroTopic.GDP, re.compile(r"\b(gdp|gross domestic product)\b", re.IGNORECASE), "GDP"),
)
FOREIGN_REGION_PATTERN = re.compile(
    r"\b(china|chinese|eurozone|euro area|european union|ecb|canada|canadian|uk|united kingdom|"
    r"britain|british|boe|germany|german|france|french|italy|italian|spain|spanish|india|indian|"
    r"japan|japanese|boj|australia|australian|rba|russia|russian|brazil|brazilian|mexico|mexican|"
    r"korea|korean|argentina|turkey|turkish|indonesia|south africa|switzerland|swiss|sweden|"
    r"norway|new zealand|rbnz|singapore|hong kong|taiwan|philippines|vietnam|thailand|"
    r"poland|netherlands|dutch|nigeria|egypt|saudi|uae|israel|chile|colombia|peru)\b",
    re.IGNORECASE,
)
# Titles that mention a macro institution but do not settle on an economic statistic.
NON_STATISTIC_PATTERN = re.compile(
    r"\b(posts? on x|tweets?|tweeted|mentions?|say(?:s)? the word|press conference|"
    r"nominee|nomination|chair(?:man)?\b.*\b(?:resign|fired|removed|leave)|approval rating)\b",
    re.IGNORECASE,
)


def classify_macro_title(title: str) -> tuple[MacroTopic, str] | None:
    normalized = " ".join(title.split())
    if NON_STATISTIC_PATTERN.search(normalized):
        return None
    for topic, pattern, basis in TOPIC_PATTERNS:
        if pattern.search(normalized):
            if FOREIGN_REGION_PATTERN.search(normalized):
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
                close_time_verified=True,
                venue_close_raw=str(market.get("close_time") or "") or None,
                strike=float(market["floor_strike"]) if market.get("floor_strike") is not None else None,
                strike_type=str(market.get("strike_type") or "") or None,
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
                # Gamma endDate can encode a wall-clock ET rule as if it were UTC.
                # Keep it unusable until the natural-language rule is reconciled.
                closes_at=None,
                outcome_labels=tuple(str(value) for value in labels),
                outcome_token_ids=tuple(str(value) for value in tokens),
                match_basis=basis,
                venue_close_raw=str(market.get("endDate") or market.get("end_date_iso") or "")
                or None,
            )
        )
    return candidates
