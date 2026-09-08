from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from forecast_macro.data.alfred import AlfredClient
from forecast_macro.datasets import load_fomc_history, scheduled_meetings
from forecast_macro.live_comparison import (
    build_comparison,
    kalshi_event_ticker,
    latest_ladder_record,
    market_cut_probability,
    model_three_way_probabilities,
    next_scheduled_meeting,
)
from forecast_macro.release_schedule import load_release_schedule
from forecast_macro.snapshots import build_feature_snapshot_with_fallback


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record today's model cut probability next to the market's (no signals)"
    )
    parser.add_argument("--meetings", type=Path, default=Path("data/fomc_meetings_2019_2026.csv"))
    parser.add_argument(
        "--training-snapshots",
        type=Path,
        default=Path("data/generated/fomc_feature_snapshots_2019_2026.json"),
    )
    parser.add_argument("--price-snapshots", type=Path, default=Path("data/generated/market_prices"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/generated/fed_market_comparisons"))
    args = parser.parse_args()

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise SystemExit("FRED_API_KEY is required; never commit it to the repository")

    as_of = datetime.now(UTC)
    schedule = load_release_schedule()
    meeting = next_scheduled_meeting(schedule, as_of=as_of)
    client = AlfredClient(api_key, request_interval=0.6)
    # ALFRED rejects a vintage date that is still "tomorrow" on FRED's Chicago clock (HTTP
    # 500); the helper uses the Chicago date and steps back a day if needed.
    snapshot = build_feature_snapshot_with_fallback(
        client,
        meeting_date=meeting.release_at.date(),
        as_of=as_of,
        build_commit=os.environ.get("GITHUB_SHA", ""),
    )

    training = scheduled_meetings(load_fomc_history(args.meetings))
    training_snapshots = json.loads(args.training_snapshots.read_text(encoding="utf-8"))
    heuristic_vector, logistic_vector = model_three_way_probabilities(
        snapshot, training, training_snapshots
    )
    heuristic, logistic = heuristic_vector["cut"], logistic_vector["cut"]

    market = None
    found = latest_ladder_record(args.price_snapshots, event_ticker=kalshi_event_ticker(meeting.release_at.date()))
    if found is not None:
        record, source = found
        market = market_cut_probability(record, current_upper=snapshot.policy_rate_upper, source_file=source)

    comparison = build_comparison(
        as_of=as_of,
        meeting=meeting,
        snapshot=snapshot,
        heuristic_cut=heuristic,
        logistic_cut=logistic,
        training_size=len(training),
        market=market,
        heuristic_three_way=heuristic_vector,
        logistic_three_way=logistic_vector,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"fed_comparison_{as_of.strftime('%Y%m%dT%H%M%SZ')}.json"
    output.write_text(json.dumps(comparison.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in comparison.to_dict().items() if k != "features"}, indent=2))


if __name__ == "__main__":
    main()
