from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from forecast_macro.data.alfred import AlfredClient
from forecast_macro.models.core_cpi import CPI_MEASURES, core_cpi_yoy_history
from forecast_macro.models.unemployment import MonthlyRate
from forecast_macro.unemployment_scoring import (
    final_record_per_release,
    score_unemployment_comparisons,
)


def first_published_yoy(client: AlfredClient, records, series_id: str) -> dict[str, float]:
    """CPI YoY for each reference month as first published (levels at the release-date vintage)."""
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
            series_id,
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
    parser.add_argument("--comparisons", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--measure", choices=tuple(CPI_MEASURES), default="core")
    args = parser.parse_args()
    series_id, _version, _series, default_dir, prefix = CPI_MEASURES[args.measure]
    comparisons = args.comparisons or Path("data/generated") / default_dir
    output = args.output or Path("data/generated") / f"{args.measure}_cpi_market_scoring.json"

    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(comparisons.glob(f"{prefix}_*.json"))]
    api_key = os.environ.get("FRED_API_KEY")
    realized: dict[str, float] = {}
    if records and api_key:
        realized = first_published_yoy(AlfredClient(api_key, request_interval=0.6), records, series_id)
    scorecard = score_unemployment_comparisons(records, realized=realized)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(scorecard.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in scorecard.to_dict().items() if k != "records"}, indent=2))


if __name__ == "__main__":
    main()
