from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from forecast_macro.data.polymarket import PolymarketPublicClient
from forecast_macro.market_review import review_market_candidates
from forecast_macro.market_rules import (
    effective_resolution_source,
    identify_contract_series,
    validate_official_rules,
    verified_rule_metadata,
)
from forecast_macro.release_schedule import load_release_schedule, verify_close_time

# The statistic each *contract-facing* model settles on. These are not the Fed-model features:
# the Fed baseline reads CPIAUCNS YoY NSA as an input, but the CPI bucket model (models/cpi.py)
# forecasts headline MoM SA, which is what a CPI contract would be compared against (R6-L2).
MODEL_SERIES = {
    "cpi": "headline_cpi_mom_sa",
    "unemployment": "unemployment_rate_sa",
    "fed_rate": "federal_funds_target_range",
    "gdp": "real_gdp",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and verify candidate contract rules")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = json.loads(args.input.read_text(encoding="utf-8"))
    client = PolymarketPublicClient()
    schedule = load_release_schedule()
    metadata = {}
    evidence = {}
    for row in rows:
        market_id = str(row["venue_market_id"])
        if row.get("venue") != "polymarket":
            evidence[market_id] = {"blockers": ["venue rule adapter is not implemented"]}
            continue
        try:
            document = client.market_rules(market_id)
            topic = str(row["topic"])
            expected_series = MODEL_SERIES[topic]
            blockers = validate_official_rules(
                document, topic=topic, expected_series=expected_series
            )
            source, origin = effective_resolution_source(document, topic=topic)
            evidence[market_id] = {
                "resolution_source": source,
                "resolution_source_origin": origin,
                "rules_source_level": document.rules_source_level,
                "contract_series": identify_contract_series(document, topic=topic),
                "expected_series": expected_series,
                "rules_text_hash": document.rules_text_hash,
                "rules_version": document.rules_version,
                "venue_updated_at": document.venue_updated_at,
                "fetched_at": document.fetched_at,
                "blockers": list(blockers),
            }
            verified = verified_rule_metadata(
                document, topic=topic, expected_series=expected_series
            )
            if verified is not None:
                metadata[market_id] = verified
            # Close time comes from the official calendar, never from the venue alone.
            close = verify_close_time(
                topic=topic,
                rule_text=f"{document.question} {document.description}",
                venue_close_raw=row.get("venue_close_raw"),
                schedule=schedule,
            )
            row["close_time_verified"] = close.verified
            row["outcome_at"] = close.outcome_at.isoformat() if close.outcome_at else None
            row["closes_at"] = close.closes_at.isoformat() if close.closes_at else None
            evidence[market_id]["close_time"] = {
                "verified": close.verified,
                "outcome_at": row["outcome_at"],
                "closes_at": row["closes_at"],
                "venue_close_raw": row.get("venue_close_raw"),
                "venue_close_interpretation": close.venue_close_interpretation,
                "blockers": list(close.blockers),
            }
        except Exception as error:  # noqa: BLE001 - fail closed on any venue/parse failure
            evidence[market_id] = {"blockers": [f"rule fetch failed: {type(error).__name__}"]}

    reviews = review_market_candidates(rows, rule_metadata=metadata)
    counts = Counter(review.status.value for review in reviews)
    result = {
        "summary": dict(sorted(counts.items())),
        "approved_contracts": counts.get("approved", 0),
        # Contract approval only unlocks price collection. D-007/D-012: signals stay off
        # until out-of-sample skill against market prices is demonstrated.
        "signal_eligible": False,
        "signal_eligible_reason": "no market-baseline Brier skill established (D-007)",
        "rule_evidence": evidence,
        "reviews": [review.to_dict() for review in reviews],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"verified rules for {len(reviews)} candidates; approved {counts.get('approved', 0)}")


if __name__ == "__main__":
    main()
