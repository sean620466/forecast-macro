from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

from forecast_macro.data.alfred import AlfredClient
from forecast_macro.unemployment_scoring import (
    final_record_per_release,
    load_unemployment_records,
    score_unemployment_comparisons,
)


def first_published_rates(client: AlfredClient, records) -> dict[str, float]:
    """UNRATE for each reference month as it stood on its release date (ALFRED vintage)."""
    realized: dict[str, float] = {}
    now = datetime.now(UTC)
    for (period, _venue), record in final_record_per_release(records).items():
        if period in realized:
            continue
        release_at = datetime.fromisoformat(str(record["release_at"]))
        if release_at > now:
            continue
        month = date(int(period[:4]), int(period[5:7]), 1)
        rows = client.observations_as_of(
            "UNRATE", vintage_date=release_at.date(), observation_start=month, observation_end=month
        )
        if rows:
            realized[period] = rows[-1].value
    return realized


def main() -> None:
    parser = argparse.ArgumentParser(description="Score unemployment comparisons against first-published rates")
    parser.add_argument("--comparisons", type=Path, default=Path("data/generated/unemployment_market_comparisons"))
    parser.add_argument("--output", type=Path, default=Path("data/generated/unemployment_market_scoring.json"))
    args = parser.parse_args()

    records = load_unemployment_records(args.comparisons)
    api_key = os.environ.get("FRED_API_KEY")
    realized: dict[str, float] = {}
    if records and api_key:
        realized = first_published_rates(AlfredClient(api_key, request_interval=0.6), records)
    scorecard = score_unemployment_comparisons(records, realized=realized)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scorecard.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in scorecard.to_dict().items() if k != "records"}, indent=2))


if __name__ == "__main__":
    main()
