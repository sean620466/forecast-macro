from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from forecast_macro.data.kalshi import KalshiEventClient, parse_kalshi_market_quote
from forecast_macro.data.polymarket import (
    PolymarketPublicClient,
    book_updated_at,
    parse_polymarket_orderbooks,
)
from forecast_macro.price_snapshots import (
    approved_events,
    is_ladder_event,
    price_event,
    price_ladder_event,
    review_from_row,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record normalized YES prices for fully approved macro events"
    )
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True, help="verify_market_rules output")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    review = json.loads(args.review.read_text(encoding="utf-8"))
    reviews_by_market = {
        str(row["venue_market_id"]): review_from_row(row) for row in review["reviews"]
    }
    evidence = review.get("rule_evidence", {})
    rules_hashes = {
        market_id: str(item.get("rules_text_hash") or "") for market_id, item in evidence.items()
    }
    outcome_by_market = {
        market_id: (item.get("close_time") or {}).get("outcome_at")
        for market_id, item in evidence.items()
    }

    events = approved_events(candidates, review["reviews"])
    client = PolymarketPublicClient()
    kalshi = KalshiEventClient()
    records = []
    for (venue, event_id), members in sorted(events.items()):
        outcome_raw = next(
            (outcome_by_market.get(m.venue_market_id) for m in members if outcome_by_market.get(m.venue_market_id)),
            None,
        )
        outcome_at = datetime.fromisoformat(outcome_raw) if outcome_raw else None
        if venue == "kalshi" and is_ladder_event(members):
            try:
                markets, observed_at = kalshi.event_markets(event_id)
                quotes = {
                    str(m["ticker"]): parse_kalshi_market_quote(m, observed_at=observed_at)
                    for m in markets
                }
            except (httpx.HTTPError, ValueError, KeyError) as error:
                records.append(
                    {
                        "venue": venue,
                        "venue_event_id": event_id,
                        "observed_at": datetime.now(UTC).isoformat(),
                        "rejected_reason": f"quote fetch failed: {type(error).__name__}: {error}",
                        "signal_eligible": False,
                    }
                )
                continue
            records.append(
                price_ladder_event(
                    members, reviews_by_market, quotes, rules_hashes, as_of=observed_at, outcome_at=outcome_at
                ).to_dict()
            )
            continue
        if venue != "polymarket":
            records.append(
                {
                    "venue": venue,
                    "venue_event_id": event_id,
                    "rejected_reason": "venue pricing adapter is not implemented",
                    "signal_eligible": False,
                }
            )
            continue
        tokens = [m.outcome_token_ids[0] for m in members]
        try:
            payload, observed_at = client.raw_orderbooks(tokens)
            quotes = parse_polymarket_orderbooks(payload, observed_at=observed_at)
            updated = book_updated_at(payload)
        except (httpx.HTTPError, ValueError, KeyError) as error:
            records.append(
                {
                    "venue": venue,
                    "venue_event_id": event_id,
                    "observed_at": datetime.now(UTC).isoformat(),
                    "rejected_reason": f"orderbook fetch failed: {type(error).__name__}: {error}",
                    "signal_eligible": False,
                }
            )
            continue
        record = price_event(
            members,
            reviews_by_market,
            quotes,
            rules_hashes,
            as_of=observed_at,
            outcome_at=outcome_at,
            book_updated_at=updated,
        )
        records.append(record.to_dict())

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"market_prices_{stamp}.json"
    output.write_text(json.dumps(records, indent=2, default=str) + "\n", encoding="utf-8")
    priced = sum(1 for r in records if r.get("probabilities"))
    print(f"wrote {len(records)} event records ({priced} priced) to {output}")
    for record in records:
        if record.get("rejected_reason"):
            print(f"WARNING: {record['venue']}/{record['venue_event_id']}: {record['rejected_reason']}")


if __name__ == "__main__":
    main()
