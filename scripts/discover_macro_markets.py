from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from forecast_macro.data.kalshi import KalshiPublicClient
from forecast_macro.data.polymarket import PolymarketPublicClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover macro prediction-market candidates")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    candidates = KalshiPublicClient().discover_open_macro_markets()
    polymarket = PolymarketPublicClient()
    for query in ("Fed interest rates", "CPI inflation", "unemployment rate", "GDP"):
        candidates.extend(polymarket.search_macro_markets(query))

    unique = {
        (candidate.venue, candidate.venue_market_id): candidate for candidate in candidates
    }
    rows = [asdict(candidate) for candidate in unique.values()]
    rows.sort(key=lambda row: (str(row["topic"]), str(row["venue"]), str(row["title"])))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} review-required market candidates to {args.output}")


if __name__ == "__main__":
    main()
