from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

from forecast_macro.cpi_backtest import backtest_cpi_baselines
from forecast_macro.data.alfred import AlfredClient
from forecast_macro.models.core_cpi import CPI_MEASURES
from forecast_macro.models.unemployment import MonthlyRate
from forecast_macro.snapshots import latest_safe_vintage

HISTORY_START = date(1980, 1, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest the empirical-change and base-effect CPI YoY baselines")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2000, 1, 1))
    parser.add_argument("--output", type=Path, default=Path("data/generated/cpi_baseline_backtest.json"))
    args = parser.parse_args()

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise SystemExit("FRED_API_KEY is required; never commit it to the repository")
    client = AlfredClient(api_key, request_interval=0.6)
    vintage = latest_safe_vintage(datetime.now(UTC))
    results = {}
    for measure, (series_id, _version, _series, _dir, _prefix) in CPI_MEASURES.items():
        rows = client.observations_as_of(
            series_id, vintage_date=vintage, observation_start=HISTORY_START, observation_end=vintage
        )
        levels = [MonthlyRate(month=r.observed_at, value=r.value) for r in rows]
        report = backtest_cpi_baselines(levels, series_id=series_id, start=args.start)
        results[measure] = report.to_dict()
        summary = {k: v for k, v in results[measure].items() if k != "records"}
        print(measure, json.dumps(summary, indent=2))
    payload = {"vintage": vintage.isoformat(), "built_at": datetime.now(UTC).isoformat(), "measures": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
