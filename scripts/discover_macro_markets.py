from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

from forecast_macro.data.kalshi import KalshiPublicClient
from forecast_macro.data.polymarket import PolymarketPublicClient
from forecast_macro.market_discovery import MarketCandidate

POLYMARKET_QUERIES = ("Fed interest rates", "CPI inflation", "unemployment rate", "GDP")


def _describe(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        return f"HTTP {error.response.status_code} from {error.request.url.host}"
    return f"{type(error).__name__}: {error}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover macro prediction-market candidates")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--status-output",
        type=Path,
        default=None,
        help="Where to write per-venue counts and errors (default: <output>.status.json)",
    )
    args = parser.parse_args()
    status_path = args.status_output or args.output.with_suffix(".status.json")

    candidates: list[MarketCandidate] = []
    errors: dict[str, str] = {}
    venue_counts: dict[str, int] = {}

    # Each venue fails independently and is recorded rather than aborting the run.
    # A venue error means "no candidates from that venue", which the review gate treats
    # as nothing to approve; it never makes a market look verified.
    try:
        kalshi = KalshiPublicClient().discover_open_macro_markets()
        candidates.extend(kalshi)
        venue_counts["kalshi"] = len(kalshi)
    except (httpx.HTTPError, ValueError) as error:
        errors["kalshi"] = _describe(error)

    polymarket = PolymarketPublicClient()
    polymarket_found: list[MarketCandidate] = []
    for query in POLYMARKET_QUERIES:
        try:
            polymarket_found.extend(polymarket.search_macro_markets(query))
        except (httpx.HTTPError, ValueError) as error:
            errors[f"polymarket:{query}"] = _describe(error)
    candidates.extend(polymarket_found)
    venue_counts["polymarket"] = len(polymarket_found)

    unique = {
        (candidate.venue, candidate.venue_market_id): candidate for candidate in candidates
    }
    rows = [asdict(candidate) for candidate in unique.values()]
    rows.sort(key=lambda row: (str(row["topic"]), str(row["venue"]), str(row["title"])))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2, default=str) + "\n", encoding="utf-8")

    status = {
        "discovered_at": datetime.now(UTC).isoformat(),
        "unique_candidates": len(rows),
        "venue_counts": venue_counts,
        "errors": errors,
        "complete": not errors,
    }
    status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} review-required market candidates to {args.output}")
    for venue, message in errors.items():
        print(f"WARNING: {venue} discovery failed: {message}")
    if errors and not rows:
        raise SystemExit("every venue failed; nothing to review")


if __name__ == "__main__":
    main()
