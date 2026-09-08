from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from forecast_macro.data.polymarket import PolymarketPublicClient
from forecast_macro.market_review import review_market_candidates
from forecast_macro.market_rules import validate_official_rules, verified_rule_metadata

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
            evidence[market_id] = {
                "resolution_source": document.resolution_source,
                "rules_text_hash": document.rules_text_hash,
                "rules_version": document.rules_version,
                "blockers": list(blockers),
            }
            verified = verified_rule_metadata(
                document, topic=topic, expected_series=expected_series
            )
            if verified is not None:
                metadata[market_id] = verified
        except Exception as error:  # noqa: BLE001 - fail closed on any venue/parse failure
            evidence[market_id] = {"blockers": [f"rule fetch failed: {type(error).__name__}"]}

    reviews = review_market_candidates(rows, rule_metadata=metadata)
    counts = Counter(review.status.value for review in reviews)
    result = {
        "summary": dict(sorted(counts.items())),
        "signal_eligible": counts.get("approved", 0) > 0,
        "rule_evidence": evidence,
        "reviews": [review.to_dict() for review in reviews],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"verified rules for {len(reviews)} candidates; approved {counts.get('approved', 0)}")


if __name__ == "__main__":
    main()
