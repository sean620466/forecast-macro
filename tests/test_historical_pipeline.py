from datetime import UTC, date, datetime, time, timedelta

import httpx
import pytest

from forecast_macro.data.alfred import AlfredClient
from forecast_macro.features import ReleasedValue, build_fomc_snapshot, released_value_from_vintage
from forecast_macro.fomc import FomcMeeting, RateDecision, label_rate_decision


def released(name: str, value: float, when: datetime) -> ReleasedValue:
    return ReleasedValue(
        name=name,
        value=value,
        released_at=when,
        vintage="2026-01-01",
        vintage_verified=True,
    )


def test_fomc_labels_cut_hold_and_hike():
    assert label_rate_decision(upper_before=5.5, upper_after=5.25) is RateDecision.CUT
    assert label_rate_decision(upper_before=5.5, upper_after=5.5) is RateDecision.HOLD
    assert label_rate_decision(upper_before=5.25, upper_after=5.5) is RateDecision.HIKE


def test_fomc_change_is_in_basis_points():
    meeting = FomcMeeting(datetime(2026, 1, 1, tzinfo=UTC), 5.5, 5.25)
    assert meeting.change_bps == -25


def test_snapshot_calculates_unemployment_change():
    cutoff = datetime(2026, 6, 1, tzinfo=UTC)
    available_before = cutoff - timedelta(seconds=1)
    snapshot = build_fomc_snapshot(
        forecast_at=cutoff,
        inflation_yoy=released("inflation_yoy", 2.4, available_before),
        unemployment_rate=released("unemployment_rate", 4.3, available_before),
        unemployment_3m_ago=released("unemployment_3m_ago", 4.0, available_before),
        policy_rate=released("policy_rate", 4.5, available_before),
    )
    assert snapshot.unemployment_change_3m == pytest.approx(0.3)
    assert snapshot.vintages["inflation_yoy"] == "2026-01-01"


def test_snapshot_rejects_future_release():
    cutoff = datetime(2026, 6, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="inflation_yoy"):
        build_fomc_snapshot(
            forecast_at=cutoff,
            inflation_yoy=released("inflation_yoy", 2.4, cutoff + timedelta(seconds=1)),
            unemployment_rate=released("unemployment_rate", 4.3, cutoff),
            unemployment_3m_ago=released("unemployment_3m_ago", 4.0, cutoff),
            policy_rate=released("policy_rate", 4.5, cutoff),
        )


def test_alfred_client_sends_vintage_date(monkeypatch):
    captured = {}

    def fake_get(url, *, params, timeout):
        captured.update(params)
        return httpx.Response(
            200,
            json={
                "observations": [
                    {
                        "date": "2025-12-01",
                        "realtime_start": "2026-01-15",
                        "realtime_end": "2026-01-15",
                        "value": "2.7",
                    }
                ]
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    rows = AlfredClient("test-key").observations_as_of(
        "CPIAUCSL", vintage_date=date(2026, 1, 15)
    )
    assert captured["vintage_dates"] == "2026-01-15"
    assert rows[0].value == 2.7
    assert rows[0].realtime_start == date(2026, 1, 15)
    value = released_value_from_vintage(rows[0], name="cpi", release_time=time(8, 30))
    assert value.vintage_verified
    assert value.released_at.hour == 8


def test_direct_released_value_is_not_vintage_verified():
    cutoff = datetime(2026, 6, 1, tzinfo=UTC)
    raw = ReleasedValue("inflation_yoy", 2.4, cutoff - timedelta(days=1), "manual")
    assert not raw.vintage_verified


def test_first_release_date_is_none_when_fred_rejects_the_history_query(monkeypatch):
    import httpx

    from forecast_macro.data.alfred import AlfredClient

    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        request = httpx.Request("GET", url)
        if params.get("realtime_start") == "1776-07-04" and params["series_id"] == "DFEDTARU":
            return httpx.Response(400, request=request, json={"error_message": "Bad Request"})
        return httpx.Response(
            200,
            request=request,
            json={"observations": [
                {"date": "2026-06-01", "value": "333.9", "realtime_start": "2026-07-14", "realtime_end": "2026-08-11"},
                {"date": "2026-06-01", "value": "333.952", "realtime_start": "2026-08-12", "realtime_end": "9999-12-31"},
            ]},
        )

    monkeypatch.setattr("forecast_macro.data.alfred.httpx.get", fake_get)
    client = AlfredClient("key")
    from datetime import date

    assert client.first_release_date("CPIAUCNS", date(2026, 6, 1)) == date(2026, 7, 14)
    assert client.first_release_date("DFEDTARU", date(2019, 1, 28)) is None
