from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from forecast_macro.market_review import review_market_candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Review discovered macro-market candidates")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = json.loads(args.input.read_text(encoding="utf-8"))
    reviews = review_market_candidates(rows)
    counts = Counter(review.status.value for review in reviews)
    result = {
        "summary": dict(sorted(counts.items())),
        "signal_eligible": counts.get("approved", 0) > 0,
        "reviews": [review.to_dict() for review in reviews],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"reviewed {len(reviews)} candidates; approved {counts.get('approved', 0)}")


if __name__ == "__main__":
    main()
