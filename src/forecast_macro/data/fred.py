from __future__ import annotations

from datetime import datetime, timezone

import httpx

from forecast_macro.types import Observation

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"


class FredClient:
    def __init__(self, api_key: str, timeout: float = 15.0) -> None:
        if not api_key:
            raise ValueError("FRED_API_KEY is required")
        self.api_key = api_key
        self.timeout = timeout

    def latest(self, series_id: str) -> Observation:
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
        }
        response = httpx.get(FRED_OBSERVATIONS_URL, params=params, timeout=self.timeout)
        response.raise_for_status()
        rows = response.json().get("observations", [])
        if not rows or rows[0]["value"] == ".":
            raise ValueError(f"No usable observation for {series_id}")

        row = rows[0]
        return Observation(
            series_id=series_id,
            value=float(row["value"]),
            observed_at=datetime.fromisoformat(row["date"]).replace(tzinfo=timezone.utc),
        )
