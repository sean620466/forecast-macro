from __future__ import annotations

import argparse
import json
from pathlib import Path

from forecast_macro.datasets import load_fomc_history, scheduled_meetings
from forecast_macro.fed_backtest import run_fed_baseline_backtest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the first vintage-safe Fed baseline backtest")
    parser.add_argument("--meetings", type=Path, required=True)
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmup", type=int, default=8)
    parser.add_argument(
        "--event-scope",
        choices=("all", "scheduled"),
        default="all",
        help="Include emergency decisions or evaluate scheduled meetings only",
    )
    args = parser.parse_args()

    meetings = load_fomc_history(args.meetings)
    if args.event_scope == "scheduled":
        meetings = scheduled_meetings(meetings)
    snapshots = json.loads(args.snapshots.read_text(encoding="utf-8"))
    report = run_fed_baseline_backtest(meetings, snapshots, warmup=args.warmup)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.to_dict().items() if key != "predictions"}, indent=2))


if __name__ == "__main__":
    main()
