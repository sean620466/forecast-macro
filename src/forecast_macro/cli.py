from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime

from forecast_macro.models.fed import rate_cut_probability
from forecast_macro.signals import compare_to_market


def main() -> None:
    parser = argparse.ArgumentParser(description="FORECAST MACRO MVP")
    parser.add_argument("--inflation", type=float, required=True)
    parser.add_argument("--unemployment", type=float, required=True)
    parser.add_argument("--unemployment-change-3m", type=float, required=True)
    parser.add_argument("--policy-rate", type=float, required=True)
    parser.add_argument("--market-cut", type=float, required=True)
    parser.add_argument("--threshold", type=float, default=0.08)
    parser.add_argument(
        "--allow-uncalibrated-signal",
        action="store_true",
        help="Explicitly display baseline signals before calibration (research only)",
    )
    args = parser.parse_args()

    model = rate_cut_probability(
        inflation_yoy=args.inflation,
        unemployment_rate=args.unemployment,
        unemployment_change_3m=args.unemployment_change_3m,
        policy_rate=args.policy_rate,
    )
    market = {"cut": args.market_cut, "hold_or_hike": 1.0 - args.market_cut}
    result = compare_to_market(
        model,
        market,
        threshold=args.threshold,
        calibrated=args.allow_uncalibrated_signal,
    )
    payload = {
        "model_version": "fed-baseline-0.1-uncalibrated",
        "computed_at": datetime.now(UTC).isoformat(),
        "status": "research_only_uncalibrated",
        "inputs": {
            "inflation_yoy": args.inflation,
            "unemployment_rate": args.unemployment,
            "unemployment_change_3m": args.unemployment_change_3m,
            "policy_rate": args.policy_rate,
            "market_cut": args.market_cut,
        },
        "signals": [asdict(item) for item in result],
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
