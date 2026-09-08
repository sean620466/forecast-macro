from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from forecast_macro.data.alfred import AlfredClient
from forecast_macro.models.unemployment import MonthlyRate
from forecast_macro.release_schedule import load_release_schedule
from forecast_macro.unemployment_comparison import (
    build_unemployment_comparison,
    latest_unemployment_record,
    next_employment_release,
)

HISTORY_START = date(1990, 1, 1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record the empirical unemployment bucket baseline next to the market (no signals)"
    )
    parser.add_argument("--price-snapshots", type=Path, default=Path("data/generated/market_prices"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/generated/unemployment_market_comparisons")
    )
    args = parser.parse_args()

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise SystemExit("FRED_API_KEY is required; never commit it to the repository")

    as_of = datetime.now(UTC)
    release = next_employment_release(load_release_schedule(), as_of=as_of)
    found = latest_unemployment_record(args.price_snapshots, release_at=release.release_at)
    if found is None:
        print(f"no priced unemployment market settling on {release.release_at.isoformat()}; nothing recorded")
        return
    record, source = found

    vintage = as_of.astimezone(ZoneInfo("America/New_York")).date()
    client = AlfredClient(api_key, request_interval=0.6)
    observations = client.observations_as_of(
        "UNRATE", vintage_date=vintage, observation_start=HISTORY_START, observation_end=vintage
    )
    history = [MonthlyRate(month=row.observed_at, value=row.value) for row in observations]

    comparison = build_unemployment_comparison(
        as_of=as_of,
        release=release,
        history=history,
        history_vintage=vintage.isoformat(),
        record=record,
        source_file=source,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"unemployment_comparison_{as_of.strftime('%Y%m%dT%H%M%SZ')}.json"
    output.write_text(json.dumps(comparison.to_dict(), indent=2) + "\n", encoding="utf-8")
    summary = comparison.to_dict()
    print(json.dumps({k: summary[k] for k in ("release_at", "latest_rate", "latest_month", "model", "market", "edge")}, indent=2))


if __name__ == "__main__":
    main()
