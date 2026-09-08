from __future__ import annotations

import argparse
import json
from pathlib import Path

from forecast_macro.comparison_scoring import load_comparison_records, score_comparisons
from forecast_macro.datasets import load_fomc_history, scheduled_meetings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score recorded model-vs-market comparisons against realized FOMC decisions"
    )
    parser.add_argument("--comparisons", type=Path, default=Path("data/generated/fed_market_comparisons"))
    parser.add_argument("--meetings", type=Path, default=Path("data/fomc_meetings_2019_2026.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/generated/fed_market_scoring.json"))
    args = parser.parse_args()

    records = load_comparison_records(args.comparisons)
    meetings = scheduled_meetings(load_fomc_history(args.meetings))
    scorecard = score_comparisons(records, meetings=meetings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scorecard.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in scorecard.to_dict().items() if k != "records"}, indent=2))


if __name__ == "__main__":
    main()
