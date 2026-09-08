from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from forecast_macro.data.alfred import AlfredClient
from forecast_macro.models.core_cpi import BASE_EFFECT_MEASURES, CPI_MEASURES, core_cpi_yoy_history
from forecast_macro.models.cpi_base_effect import base_effect_change_distribution
from forecast_macro.models.unemployment import MonthlyRate
from forecast_macro.release_schedule import load_release_schedule
from forecast_macro.snapshots import latest_safe_vintage
from forecast_macro.unemployment_comparison import (
    build_unemployment_comparison,
    latest_bucket_record,
    next_release,
)

VENUES = ("polymarket", "kalshi")
HISTORY_START = date(1989, 1, 1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record the empirical Core CPI YoY bucket baseline next to the market (no signals)"
    )
    parser.add_argument("--price-snapshots", type=Path, default=Path("data/generated/market_prices"))
    parser.add_argument("--output-dir", type=Path, default=None, help="default depends on --measure")
    parser.add_argument("--measure", choices=tuple(CPI_MEASURES), default="core")
    args = parser.parse_args()
    series_id, model_version, contract_series, default_dir, prefix = CPI_MEASURES[args.measure]
    output_dir = args.output_dir or Path("data/generated") / default_dir

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise SystemExit("FRED_API_KEY is required; never commit it to the repository")

    as_of = datetime.now(UTC)
    release = next_release(load_release_schedule(), as_of=as_of, series="cpi")
    found_by_venue = {}
    for venue in VENUES:
        # Polymarket's approved CPI event predates the contract_series field on price records
        # (task 40); the rules check identified it as core, so the filter applies only where
        # the record carries the field.
        found = latest_bucket_record(
            args.price_snapshots,
            release_at=release.release_at,
            topic="cpi",
            venue=venue,
            contract_series=contract_series if venue == "kalshi" else None,
        )
        # Legacy Polymarket records without the field are core (the only approved Polymarket CPI
        # event); they must never be scored as headline.
        accepted = (None, contract_series) if args.measure == "core" else (contract_series,)
        if found is not None and found[0].get("contract_series") in accepted:
            found_by_venue[venue] = found
    if not found_by_venue:
        print(f"no priced {args.measure} CPI market settling on {release.release_at.isoformat()}; nothing recorded")
        return

    vintage = latest_safe_vintage(as_of)
    client = AlfredClient(api_key, request_interval=0.6)
    try:
        observations = client.observations_as_of(
            series_id, vintage_date=vintage, observation_start=HISTORY_START, observation_end=vintage
        )
    except httpx.HTTPStatusError as error:
        if error.response.status_code != 500:
            raise
        vintage = vintage - timedelta(days=1)
        observations = client.observations_as_of(
            series_id, vintage_date=vintage, observation_start=HISTORY_START, observation_end=vintage
        )
    levels = [MonthlyRate(month=row.observed_at, value=row.value) for row in observations]
    history = core_cpi_yoy_history(levels)
    change_distribution = None
    if args.measure in BASE_EFFECT_MEASURES:
        # Base effect explicit: known L[t]/L[t-11] times a seasonal-mean-plus-residual MoM draw.
        change_distribution = base_effect_change_distribution(levels, latest_yoy=history[-1].value)

    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = as_of.strftime("%Y%m%dT%H%M%SZ")
    for venue, (record, source) in found_by_venue.items():
        comparison = build_unemployment_comparison(
            as_of=as_of,
            release=release,
            history=history,
            history_vintage=vintage.isoformat(),
            record=record,
            source_file=source,
            model_version=model_version,
            topic="cpi",
            change_distribution=change_distribution,
        )
        suffix = "" if venue == "polymarket" else f"_{venue}"
        output = output_dir / f"{prefix}_{stamp}{suffix}.json"
        output.write_text(json.dumps(comparison.to_dict(), indent=2) + "\n", encoding="utf-8")
        summary = comparison.to_dict()
        print(json.dumps({k: summary[k] for k in ("venue", "release_at", "latest_rate", "latest_month", "model", "market", "edge")}, indent=2))


if __name__ == "__main__":
    main()
