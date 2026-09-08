from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from forecast_macro.data.alfred import AlfredClient
from forecast_macro.models.core_cpi import MODEL_VERSION, SERIES_ID, core_cpi_yoy_history
from forecast_macro.models.unemployment import MonthlyRate
from forecast_macro.release_schedule import load_release_schedule
from forecast_macro.snapshots import latest_safe_vintage
from forecast_macro.unemployment_comparison import (
    build_unemployment_comparison,
    latest_bucket_record,
    next_release,
)

HISTORY_START = date(1989, 1, 1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record the empirical Core CPI YoY bucket baseline next to the market (no signals)"
    )
    parser.add_argument("--price-snapshots", type=Path, default=Path("data/generated/market_prices"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/generated/core_cpi_market_comparisons"))
    args = parser.parse_args()

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise SystemExit("FRED_API_KEY is required; never commit it to the repository")

    as_of = datetime.now(UTC)
    release = next_release(load_release_schedule(), as_of=as_of, series="cpi")
    found = latest_bucket_record(args.price_snapshots, release_at=release.release_at, topic="cpi")
    if found is None:
        print(f"no priced Core CPI market settling on {release.release_at.isoformat()}; nothing recorded")
        return
    record, source = found

    vintage = latest_safe_vintage(as_of)
    client = AlfredClient(api_key, request_interval=0.6)
    try:
        observations = client.observations_as_of(
            SERIES_ID, vintage_date=vintage, observation_start=HISTORY_START, observation_end=vintage
        )
    except httpx.HTTPStatusError as error:
        if error.response.status_code != 500:
            raise
        vintage = vintage - timedelta(days=1)
        observations = client.observations_as_of(
            SERIES_ID, vintage_date=vintage, observation_start=HISTORY_START, observation_end=vintage
        )
    levels = [MonthlyRate(month=row.observed_at, value=row.value) for row in observations]
    history = core_cpi_yoy_history(levels)

    comparison = build_unemployment_comparison(
        as_of=as_of,
        release=release,
        history=history,
        history_vintage=vintage.isoformat(),
        record=record,
        source_file=source,
        model_version=MODEL_VERSION,
        topic="cpi",
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"core_cpi_comparison_{as_of.strftime('%Y%m%dT%H%M%SZ')}.json"
    output.write_text(json.dumps(comparison.to_dict(), indent=2) + "\n", encoding="utf-8")
    summary = comparison.to_dict()
    print(json.dumps({k: summary[k] for k in ("release_at", "latest_rate", "latest_month", "model", "market", "edge")}, indent=2))


if __name__ == "__main__":
    main()
