from __future__ import annotations

import time
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
    def __init__(
        self,
        api_key: str,
        timeout: float = 15.0,
        *,
        request_interval: float = 0.0,
        max_retries: int = 4,
    ) -> None:
        if not api_key:
            raise ValueError("FRED_API_KEY is required")
        self.api_key = api_key
        self.timeout = timeout
        self.request_interval = request_interval
        self.max_retries = max_retries
        self._last_request_at: float | None = None

    def _get(self, params: dict[str, str | int]) -> httpx.Response:
        """GET with pacing and retries.

        Retries HTTP 429 (honouring Retry-After), HTTP 5xx and transport errors (timeouts,
        connection resets) with exponential backoff. FRED returns sporadic 500s for
        perfectly valid historical vintages; a 94-meeting build must not die on one of
        them eleven minutes in. The final attempt's response (or error) is returned/raised
        unchanged so callers keep their own 500 handling for the "vintage is tomorrow"
        case.
        """
        for attempt in range(self.max_retries + 1):
            if self._last_request_at is not None:
                elapsed = time.monotonic() - self._last_request_at
                time.sleep(max(0.0, self.request_interval - elapsed))
            try:
                response = httpx.get(FRED_OBSERVATIONS_URL, params=params, timeout=self.timeout)
            except httpx.TransportError:
                self._last_request_at = time.monotonic()
                if attempt == self.max_retries:
                    raise
                time.sleep(min(2**attempt, 16))
                continue
            self._last_request_at = time.monotonic()
            retryable = response.status_code == 429 or response.status_code >= 500
            if not retryable or attempt == self.max_retries:
                return response
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else min(2**attempt, 16)
            time.sleep(delay)
        raise AssertionError("retry loop must return")

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

        response = self._get(params)
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


    def first_release_date(self, series_id: str, observed_at: date) -> date | None:
        """Earliest real-time date on which the observation for `observed_at` was published.

        Queries the full vintage history of that single observation; the smallest
        realtime_start is its first publication. None when the observation has no vintages.
        """
        params: dict[str, str | int] = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "realtime_start": "1776-07-04",
            "realtime_end": "9999-12-31",
            "observation_start": observed_at.isoformat(),
            "observation_end": observed_at.isoformat(),
            "output_type": 1,
        }
        response = self._get(params)
        if response.status_code == 400:
            # FRED refuses the full real-time range for some series (observed for the daily
            # DFEDTARU). Provenance is optional; the feature value itself is unaffected.
            return None
        response.raise_for_status()
        starts = [
            date.fromisoformat(row["realtime_start"])
            for row in response.json().get("observations", [])
            if row.get("value") not in (None, ".")
        ]
        return min(starts) if starts else None
