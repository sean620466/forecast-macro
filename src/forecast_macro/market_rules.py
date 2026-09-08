from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from forecast_macro.market_review import ContractRuleMetadata
from forecast_macro.official_sources import (
    OFFICIAL_SOURCE_HOSTS,
    first_official_url,
    is_official_source,
)


@dataclass(frozen=True)
class MarketRuleDocument:
    market_id: str
    question: str
    description: str
    resolution_source: str
    # Content-addressed version: changes only when question, description or source change.
    rules_version: str
    rules_text_hash: str
    # Provenance. venue_updated_at churns on price/liquidity edits and is not a rules version.
    venue_updated_at: str = ""
    fetched_at: str = ""
    rules_source_level: str = "missing"  # "market" | "event" | "missing"


TOPIC_TERMS: dict[str, tuple[str, ...]] = {
    "cpi": ("cpi", "consumer price"),
    "unemployment": ("unemployment", "jobless rate"),
    "fed_rate": ("federal reserve", "fomc", "fed rate", "federal funds"),
    "gdp": ("gross domestic product", "gdp"),
}

_YOY_TERMS = ("yoy", "year-over-year", "year over year", "12-month", "12 month", "annual rate")
_MOM_TERMS = ("mom", "month-over-month", "month over month", "monthly change", "from the prior month",
              "from the previous month")
_CORE_TERMS = ("core", "excluding food and energy", "less food and energy")
_HEADLINE_TERMS = ("headline", "all items", "all-items", "cpi-u")
_NSA_TERMS = ("not seasonally adjusted", "before seasonal adjustment", "unadjusted")
_SA_TERMS = ("seasonally adjusted",)


def _any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def identify_contract_series(document: MarketRuleDocument, *, topic: str) -> str | None:
    """Name the statistic a contract settles on, or None when the text does not say explicitly.

    Every dimension needs positive evidence. A missing keyword never defaults to the model's
    own series, so an under-specified contract is blocked rather than matched (R5-H1).
    """
    text = f"{document.question} {document.description}".lower()
    if topic == "cpi":
        if _any(text, _CORE_TERMS):
            measure = "core"
        elif _any(text, _HEADLINE_TERMS) or "cpi" in text or "consumer price" in text:
            measure = "headline"
        else:
            return None
        if _any(text, _YOY_TERMS) and not _any(text, _MOM_TERMS):
            period = "yoy"
        elif _any(text, _MOM_TERMS) and not _any(text, _YOY_TERMS):
            period = "mom"
        else:
            return None
        if _any(text, _NSA_TERMS):
            adjustment = "nsa"
        elif _any(text, _SA_TERMS):
            adjustment = "sa"
        else:
            return None
        return f"{measure}_cpi_{period}_{adjustment}"
    if topic == "unemployment":
        if "unemployment rate" not in text or "u-6" in text:
            return None
        if _any(text, _NSA_TERMS):
            return "unemployment_rate_nsa"
        if _any(text, _SA_TERMS):
            return "unemployment_rate_sa"
        return None
    if topic == "fed_rate":
        if "target range" in text or "federal funds" in text or "fed funds" in text:
            return "federal_funds_target_range"
        return None
    if topic == "gdp":
        if "gdp" not in text and "gross domestic product" not in text:
            return None
        if "nominal" in text:
            return "nominal_gdp"
        if "real" in text:
            return "real_gdp"
        return None
    return None


def _rules_hash(question: str, description: str, resolution_source: str) -> str:
    canonical = json.dumps(
        {"description": description, "question": question, "resolution_source": resolution_source},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def parse_polymarket_rules(
    payload: dict[str, Any], *, fetched_at: datetime | None = None
) -> MarketRuleDocument:
    """Build a rule document from one consistent level of the Gamma payload.

    Market-level fields win when the market has its own description; otherwise the first
    event's fields are used as a whole. Fields are never mixed across levels (R6-M1).
    """
    events = payload.get("events") or []
    event = events[0] if events and isinstance(events[0], dict) else {}
    market_description = str(payload.get("description") or "").strip()
    if market_description:
        level, source_payload = "market", payload
    elif str(event.get("description") or "").strip():
        level, source_payload = "event", event
    else:
        level, source_payload = "missing", {}

    description = str(source_payload.get("description") or "").strip()
    source = str(source_payload.get("resolutionSource") or "").strip()
    venue_updated_at = str(source_payload.get("updatedAt") or "").strip()
    question = str(payload.get("question") or "").strip()
    text_hash = _rules_hash(question, description, source)
    stamp = (fetched_at or datetime.now(UTC)).isoformat()
    return MarketRuleDocument(
        market_id=str(payload.get("id") or payload.get("conditionId") or ""),
        question=question,
        description=description,
        resolution_source=source,
        rules_version=text_hash.removeprefix("sha256:")[:16],
        rules_text_hash=text_hash,
        venue_updated_at=venue_updated_at,
        fetched_at=stamp,
        rules_source_level=level,
    )


def effective_resolution_source(document: MarketRuleDocument, *, topic: str) -> tuple[str, str]:
    """Return (url, origin) where origin is 'field', 'description' or ''."""
    if document.resolution_source and is_official_source(document.resolution_source, topic=topic):
        return document.resolution_source, "field"
    if not document.resolution_source:
        from_text = first_official_url(document.description, topic=topic)
        if from_text:
            return from_text, "description"
    return document.resolution_source, ""


def validate_official_rules(
    document: MarketRuleDocument,
    *,
    topic: str,
    expected_series: str | None = None,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if not document.description:
        blockers.append("contract description is missing")
    if document.rules_source_level == "missing":
        blockers.append("no rule text at market or event level")
    if not document.fetched_at:
        blockers.append("rule snapshot time is missing")
    if topic not in OFFICIAL_SOURCE_HOSTS:
        blockers.append("unsupported macro topic")
    else:
        _, origin = effective_resolution_source(document, topic=topic)
        if not origin:
            blockers.append("resolution source is not the required official agency")
    text = f"{document.question} {document.description}".lower()
    terms = TOPIC_TERMS.get(topic, ())
    if terms and not any(term in text for term in terms):
        blockers.append("contract rules do not identify the expected macro series")
    actual_series = identify_contract_series(document, topic=topic)
    if actual_series is None:
        blockers.append("contract series could not be identified from the rule text")
    elif expected_series is not None and actual_series != expected_series:
        blockers.append(
            f"contract series {actual_series!r} does not match model series {expected_series!r}"
        )
    return tuple(blockers)


def verified_rule_metadata(
    document: MarketRuleDocument,
    *,
    topic: str,
    expected_series: str | None = None,
) -> ContractRuleMetadata | None:
    if validate_official_rules(document, topic=topic, expected_series=expected_series):
        return None
    source, origin = effective_resolution_source(document, topic=topic)
    series = identify_contract_series(document, topic=topic) or ""
    return ContractRuleMetadata(
        resolution_source=source,
        rules_text_hash=document.rules_text_hash,
        rules_version=document.rules_version,
        series_id=series,
        resolution_source_origin=origin,
        fetched_at=document.fetched_at,
    )


# Kalshi rules name the settlement source in prose rather than as a URL. Only these exact
# phrases are accepted, and the mapping is recorded as origin "rules_text_reference".
KALSHI_SOURCE_PHRASES: dict[str, str] = {
    "federal reserve's official website": "https://www.federalreserve.gov/",
    "bureau of labor statistics": "https://www.bls.gov/",
    "bureau of economic analysis": "https://www.bea.gov/",
}


def parse_kalshi_rules(
    market: dict[str, Any], *, fetched_at: datetime | None = None
) -> MarketRuleDocument:
    primary = str(market.get("rules_primary") or "").strip()
    secondary = str(market.get("rules_secondary") or "").strip()
    description = " ".join(part for part in (primary, secondary) if part)
    lowered = description.lower()
    source = next(
        (url for phrase, url in KALSHI_SOURCE_PHRASES.items() if phrase in lowered), ""
    )
    question = str(market.get("title") or "").strip()
    text_hash = _rules_hash(question, description, source)
    return MarketRuleDocument(
        market_id=str(market.get("ticker") or ""),
        question=question,
        description=description,
        resolution_source=source,
        rules_version=text_hash.removeprefix("sha256:")[:16],
        rules_text_hash=text_hash,
        venue_updated_at=str(market.get("updated_time") or "").strip(),
        fetched_at=(fetched_at or datetime.now(UTC)).isoformat(),
        rules_source_level="market" if primary else "missing",
    )
