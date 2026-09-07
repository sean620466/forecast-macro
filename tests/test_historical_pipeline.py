from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from forecast_macro.data.alfred import AlfredClient
from forecast_macro.features import ReleasedValue, build_fomc_snapshot
from forecast_macro.fomc import FomcMeeting, RateDecision, label_rate_decision


def released(name: str, value: float, when: datetime) -> ReleasedValue:
    return ReleasedValue(name=name, value=value, released_at=when, vintage="2026-01-01")


def test_fomc_labels_cut_hold_and_hike():
    assert label_rate_decision(upper_before=5.5, upper_after=5.25) is RateDecision.CUT
    assert label_rate_decision(upper_before=5.5, upper_after=5.5) is RateDecision.HOLD
    assert label_rate_decision(upper_before=5.25, upper_after=5.5) is RateDecision.HIKE


def test_fomc_change_is_in_basis_points():
    meeting = FomcMeeting(datetime(2026, 1, 1, tzinfo=UTC), 5.5, 5.25)
    assert meeting.change_bps == -25


def test_snapshot_calculates_unemployment_change():
    cutoff = datetime(2026, 6, 1, tzinfo=UTC)
    snapshot = build_fomc_snapshot(
        forecast_at=cutoff,
        inflation_yoy=released("inflation_yoy", 2.4, cutoff),
        unemployment_rate=released("unemployment_rate", 4.3, cutoff),
        unemployment_3m_ago=released("unemployment_3m_ago", 4.0, cutoff),
        policy_rate=released("policy_rate", 4.5, cutoff),
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
