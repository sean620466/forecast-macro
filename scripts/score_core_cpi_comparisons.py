from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from forecast_macro.data.alfred import AlfredClient
from forecast_macro.models.core_cpi import SERIES_ID, core_cpi_yoy_history
from forecast_macro.models.unemployment import MonthlyRate
from forecast_macro.unemployment_scoring import (
    final_record_per_release,
    score_unemployment_comparisons,
)


def first_published_yoy(client: AlfredClient, records) -> dict[str, float]:
    """Core CPI YoY for each reference month as first published (levels at the release-date vintage)."""
    realized: dict[str, float] = {}
    now = datetime.now(UTC)
    for period, record in final_record_per_release(records).items():
        release_at = datetime.fromisoformat(str(record["release_at"]))
        if release_at > now:
            continue
        month = date(int(period[:4]), int(period[5:7]), 1)
        rows = client.observations_as_of(
            SERIES_ID,
            vintage_date=release_at.date(),
            observation_start=month - timedelta(days=400),
            observation_end=month,
        )
        history = core_cpi_yoy_history([MonthlyRate(r.observed_at, r.value) for r in rows])
        match = [h for h in history if h.month == month]
        if match:
            realized[period] = match[-1].value
    return realized


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Core CPI comparisons against first-published YoY")
    parser.add_argument("--comparisons", type=Path, default=Path("data/generated/core_cpi_market_comparisons"))
    parser.add_argument("--output", type=Path, default=Path("data/generated/core_cpi_market_scoring.json"))
    args = parser.parse_args()

    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(args.comparisons.glob("core_cpi_comparison_*.json"))]
    api_key = os.environ.get("FRED_API_KEY")
    realized: dict[str, float] = {}
    if records and api_key:
        realized = first_published_yoy(AlfredClient(api_key, request_interval=0.6), records)
    scorecard = score_unemployment_comparisons(records, realized=realized)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scorecard.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in scorecard.to_dict().items() if k != "records"}, indent=2))


if __name__ == "__main__":
    main()
