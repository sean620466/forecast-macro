"""Task 37 follow-up: the ALFRED client survives transient FRED failures.

Build run #12 (94 meetings, --first-release-dates) died after eleven minutes on a single
HTTP 500 for the valid vintage 2022-01-25. The client now retries 5xx and transport
errors with backoff; the last attempt's response still surfaces so the live scripts keep
their "vintage is tomorrow" fallback.
"""
from __future__ import annotations

from datetime import date

import httpx
import pytest

from forecast_macro.data import alfred as alfred_module
from forecast_macro.data.alfred import AlfredClient


def _responses(monkeypatch, sequence):
    calls: list[int] = []

    def fake_get(url, params=None, timeout=None):
        item = sequence[min(len(calls), len(sequence) - 1)]
        calls.append(1)
        if isinstance(item, Exception):
            raise item
        request = httpx.Request("GET", url)
        body = {"observations": [
            {"date": "2022-01-01", "value": "4.0", "realtime_start": "2022-01-25", "realtime_end": "2022-01-25"}
        ]} if item == 200 else {}
        return httpx.Response(item, request=request, json=body)

    monkeypatch.setattr(alfred_module.httpx, "get", fake_get)
    monkeypatch.setattr(alfred_module.time, "sleep", lambda seconds: None)
    return calls


def test_500_is_retried_then_succeeds(monkeypatch):
    calls = _responses(monkeypatch, [500, 500, 200])
    client = AlfredClient("key", max_retries=4)
    rows = client.observations_as_of("UNRATE", vintage_date=date(2022, 1, 25))
    assert len(calls) == 3
    assert rows[0].value == 4.0


def test_persistent_500_still_raises_after_retries(monkeypatch):
    calls = _responses(monkeypatch, [500])
    client = AlfredClient("key", max_retries=2)
    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        client.observations_as_of("UNRATE", vintage_date=date(2022, 1, 25))
    assert excinfo.value.response.status_code == 500
    assert len(calls) == 3  # first attempt + two retries


def test_timeout_is_retried(monkeypatch):
    calls = _responses(monkeypatch, [httpx.ReadTimeout("slow"), 200])
    client = AlfredClient("key", max_retries=1)
    rows = client.observations_as_of("UNRATE", vintage_date=date(2022, 1, 25))
    assert len(calls) == 2 and rows


def test_400_is_not_retried(monkeypatch):
    calls = _responses(monkeypatch, [400])
    client = AlfredClient("key", max_retries=3)
    assert client.first_release_date("DFEDTARU", date(2022, 1, 25)) is None
    assert len(calls) == 1
