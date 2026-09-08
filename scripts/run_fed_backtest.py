from __future__ import annotations

import argparse
import json
from pathlib import Path

from forecast_macro.datasets import (
    load_fomc_history,
    predetermined_window_dates,
    scheduled_meetings,
    validate_continuity,
    window_meetings,
)
from forecast_macro.fed_backtest import run_fed_baseline_backtest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the first vintage-safe Fed baseline backtest")
    parser.add_argument("--meetings", type=Path, required=True)
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmup", type=int, default=8)
    parser.add_argument(
        "--event-scope",
        choices=("all", "scheduled", "window"),
        default="all",
        help=(
            "all: every decision incl. emergency; scheduled: scheduled meetings with their own "
            "change; window: scheduled meetings labelled by the change since the previous "
            "scheduled decision (contract-style)"
        ),
    )
    parser.add_argument(
        "--allow-rate-gaps",
        action="store_true",
        help="scheduled scope only: keep rows whose upper_before skips an emergency move",
    )
    args = parser.parse_args()

    meetings = load_fomc_history(args.meetings)
    if args.event_scope == "scheduled":
        meetings = scheduled_meetings(meetings)
        # Filtering removes emergency rows; refuse silently bridged rate gaps (R4-L2)
        # unless the caller states that this is intended.
        if not args.allow_rate_gaps:
            validate_continuity(meetings)
    dropped: list[str] = []
    if args.event_scope == "window":
        dropped = [value.isoformat() for value in predetermined_window_dates(meetings)]
        meetings = window_meetings(meetings)
    snapshots = json.loads(args.snapshots.read_text(encoding="utf-8"))
    report = run_fed_baseline_backtest(meetings, snapshots, warmup=args.warmup)
    payload = {"event_scope": args.event_scope, **report.to_dict()}
    if args.event_scope == "window":
        payload["dropped_predetermined_windows"] = dropped
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "predictions"}, indent=2))


if __name__ == "__main__":
    main()
