from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

import httpx

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"


@dataclass(frozen=True)
class VintageObservation:
    series_id: str
    value: float
    observed_at: date
    realtime_start: date
    realtime_end: date
    fetched_at: datetime


class AlfredClient:
    def __init__(self, api_key: str, timeout: float = 15.0) -> None:
        if not api_key:
            raise ValueError("FRED_API_KEY is required")
        self.api_key = api_key
        self.timeout = timeout

    def observations_as_of(
        self,
        series_id: str,
        *,
        vintage_date: date,
        observation_start: date | None = None,
        observation_end: date | None = None,
    ) -> list[VintageObservation]:
        params: dict[str, str | int] = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "vintage_dates": vintage_date.isoformat(),
            "output_type": 1,
        }
        if observation_start:
            params["observation_start"] = observation_start.isoformat()
        if observation_end:
            params["observation_end"] = observation_end.isoformat()

        response = httpx.get(FRED_OBSERVATIONS_URL, params=params, timeout=self.timeout)
        response.raise_for_status()
        fetched_at = datetime.now(UTC)
        result: list[VintageObservation] = []
        for row in response.json().get("observations", []):
            if row["value"] == ".":
                continue
            result.append(
                VintageObservation(
                    series_id=series_id,
                    value=float(row["value"]),
                    observed_at=date.fromisoformat(row["date"]),
                    realtime_start=date.fromisoformat(row["realtime_start"]),
                    realtime_end=date.fromisoformat(row["realtime_end"]),
                    fetched_at=fetched_at,
                )
            )
        return result
