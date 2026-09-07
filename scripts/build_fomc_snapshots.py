from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from forecast_macro.data.alfred import AlfredClient
from forecast_macro.datasets import load_fomc_history
from forecast_macro.snapshots import build_historical_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Build point-in-time FOMC feature snapshots")
    parser.add_argument("--meetings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise SystemExit("FRED_API_KEY is required; never commit it to the repository")

    client = AlfredClient(api_key)
    meetings = load_fomc_history(args.meetings)
    snapshots = [build_historical_snapshot(client, meeting).to_dict() for meeting in meetings]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshots, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(snapshots)} point-in-time snapshots to {args.output}")


if __name__ == "__main__":
    main()
