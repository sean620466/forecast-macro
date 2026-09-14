from __future__ import annotations

import argparse
import json
from pathlib import Path

from forecast_macro.comparison_scoring import load_comparison_records, score_comparisons
from forecast_macro.datasets import load_fomc_history, scheduled_meetings
from forecast_macro.fomc_decisions import (
    DEFAULT_REALIZED_PATH,
    load_realized_decisions,
    merge_decisions,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score recorded model-vs-market comparisons against realized FOMC decisions"
    )
    parser.add_argument("--comparisons", type=Path, default=Path("data/generated/fed_market_comparisons"))
    parser.add_argument("--meetings", type=Path, default=Path("data/fomc_meetings_2019_2026.csv"))
    parser.add_argument(
        "--realized",
        type=Path,
        default=DEFAULT_REALIZED_PATH,
        help="bot-recorded decisions appended to the history (scripts/record_fomc_decisions.py)",
    )
    parser.add_argument("--output", type=Path, default=Path("data/generated/fed_market_scoring.json"))
    args = parser.parse_args()

    records = load_comparison_records(args.comparisons)
    # Task 48: decisions the workflow labelled from the press release count as outcomes too.
    meetings = scheduled_meetings(
        merge_decisions(load_fomc_history(args.meetings), load_realized_decisions(args.realized))
    )
    scorecard = score_comparisons(records, meetings=meetings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scorecard.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in scorecard.to_dict().items() if k != "records"}, indent=2))


if __name__ == "__main__":
    main()
