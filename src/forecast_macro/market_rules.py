from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from forecast_macro.market_review import ContractRuleMetadata


@dataclass(frozen=True)
class MarketRuleDocument:
    market_id: str
    question: str
    description: str
    resolution_source: str
    rules_version: str
    rules_text_hash: str


OFFICIAL_SOURCE_HOSTS: dict[str, tuple[str, ...]] = {
    "cpi": ("bls.gov",),
    "unemployment": ("bls.gov",),
    "fed_rate": ("federalreserve.gov",),
    "gdp": ("bea.gov",),
}
TOPIC_TERMS: dict[str, tuple[str, ...]] = {
    "cpi": ("cpi", "consumer price"),
    "unemployment": ("unemployment", "jobless rate"),
    "fed_rate": ("federal reserve", "fomc", "fed rate"),
    "gdp": ("gross domestic product", "gdp"),
}


def identify_contract_series(document: MarketRuleDocument, *, topic: str) -> str | None:
    text = f"{document.question} {document.description}".lower()
    if topic == "cpi":
        measure = "core" if "core" in text else "headline"
        period = "yoy" if any(term in text for term in ("yoy", "12-month", "12 month")) else "mom"
        adjustment = "nsa" if any(
            term in text
            for term in ("not seasonally adjusted", "before seasonal adjustment", "unadjusted")
        ) else "sa"
        return f"{measure}_cpi_{period}_{adjustment}"
    if topic == "unemployment":
        return "unemployment_rate_sa"
    if topic == "fed_rate":
        return "federal_funds_target_range"
    if topic == "gdp":
        return "real_gdp"
    return None


def parse_polymarket_rules(payload: dict[str, Any]) -> MarketRuleDocument:
    events = payload.get("events") or []
    event = events[0] if events and isinstance(events[0], dict) else {}
    description = str(payload.get("description") or event.get("description") or "").strip()
    source = str(payload.get("resolutionSource") or event.get("resolutionSource") or "").strip()
    version = str(payload.get("updatedAt") or event.get("updatedAt") or "").strip()
    canonical = json.dumps(
        {
            "description": description,
            "question": str(payload.get("question") or "").strip(),
            "resolution_source": source,
            "rules_version": version,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return MarketRuleDocument(
        market_id=str(payload.get("id") or payload.get("conditionId") or ""),
        question=str(payload.get("question") or "").strip(),
        description=description,
        resolution_source=source,
        rules_version=version,
        rules_text_hash="sha256:" + hashlib.sha256(canonical.encode()).hexdigest(),
    )


def validate_official_rules(
    document: MarketRuleDocument,
    *,
    topic: str,
    expected_series: str | None = None,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if not document.description:
        blockers.append("contract description is missing")
    if not document.rules_version:
        blockers.append("contract rules version timestamp is missing")
    allowed_hosts = OFFICIAL_SOURCE_HOSTS.get(topic)
    if not allowed_hosts:
        blockers.append("unsupported macro topic")
    else:
        host = (urlparse(document.resolution_source).hostname or "").lower()
        if not any(host == allowed or host.endswith("." + allowed) for allowed in allowed_hosts):
            blockers.append("resolution source is not the required official agency")
    text = f"{document.question} {document.description}".lower()
    terms = TOPIC_TERMS.get(topic, ())
    if terms and not any(term in text for term in terms):
        blockers.append("contract rules do not identify the expected macro series")
    actual_series = identify_contract_series(document, topic=topic)
    if expected_series is not None and actual_series != expected_series:
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
    return ContractRuleMetadata(
        resolution_source=document.resolution_source,
        rules_text_hash=document.rules_text_hash,
        rules_version=document.rules_version,
    )
