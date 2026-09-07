from __future__ import annotations

import argparse
import json
from pathlib import Path

from forecast_macro.datasets import load_fomc_history, scheduled_meetings
from forecast_macro.fed_model_comparison import run_walk_forward_logistic


def main() -> None:
    parser = argparse.ArgumentParser(description="Run leakage-safe walk-forward Fed model")
    parser.add_argument("--meetings", type=Path, required=True)
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    meetings = scheduled_meetings(load_fomc_history(args.meetings))
    snapshots = json.loads(args.snapshots.read_text(encoding="utf-8"))
    report = run_walk_forward_logistic(meetings, snapshots)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report.to_dict(), indent=2))


if __name__ == "__main__":
    main()
