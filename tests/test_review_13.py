"""Task 13: live model-vs-market comparison for the next FOMC decision (no signals)."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from forecast_macro.data.alfred import VintageObservation
from forecast_macro.datasets import load_fomc_history, scheduled_meetings
from forecast_macro.live_comparison import (
    build_comparison,
    kalshi_event_ticker,
    latest_ladder_record,
    market_cut_probability,
    model_cut_probabilities,
    next_scheduled_meeting,
)
from forecast_macro.release_schedule import load_release_schedule
from forecast_macro.snapshots import HistoricalFeatureSnapshot, build_feature_snapshot


def observation(series: str, year: int, month: int, value: float) -> VintageObservation:
    vintage = date(2026, 9, 8)
    return VintageObservation(
        series_id=series,
        value=value,
        observed_at=date(year, month, 1),
        realtime_start=vintage,
        realtime_end=vintage,
        fetched_at=datetime(2026, 9, 8, tzinfo=UTC),
    )


class FakeAlfredClient:
    def __init__(self, series):
        self.series = series
        self.requested_vintages = []

    def observations_as_of(self, series_id, *, vintage_date, observation_start, observation_end):
        self.requested_vintages.append(vintage_date)
        return self.series[series_id]

ROOT = Path(__file__).parents[1]
SCHEDULE = load_release_schedule()
NOW = datetime(2026, 9, 8, 13, 40, tzinfo=UTC)

# Priced KXFED-26SEP ladder record as committed by the bot on 2026-09-08 02:44 UTC.
LADDER_RECORD = {
    "venue": "kalshi",
    "venue_event_id": "KXFED-26SEP",
    "observed_at": "2026-09-08T02:44:39+00:00",
    "probabilities": {
        "le_2.75": 0.005, "3.00": 0.0, "3.25": 0.0, "3.50": 0.0, "3.75": 0.47,
        "4.00": 0.51, "4.25": 0.01, "4.50": 0.0, "4.75": 0.0, "5.00": 0.0, "5.25": 0.0, "gt_5.25": 0.005,
    },
    "probability_bounds": {
        "le_2.75": [0.0, 0.01], "3.00": [0.0, 0.01], "3.25": [0.0, 0.01], "3.50": [0.0, 0.01],
        "3.75": [0.46, 0.48], "4.00": [0.50, 0.52], "4.25": [0.0, 0.02], "4.50": [0.0, 0.01],
        "4.75": [0.0, 0.01], "5.00": [0.0, 0.01], "5.25": [0.0, 0.01], "gt_5.25": [0.0, 0.01],
    },
}


def test_next_meeting_and_event_ticker() -> None:
    meeting = next_scheduled_meeting(SCHEDULE, as_of=NOW)
    assert meeting.release_at.date() == date(2026, 9, 16)
    assert kalshi_event_ticker(meeting.release_at.date()) == "KXFED-26SEP"
    assert kalshi_event_ticker(date(2027, 1, 27)) == "KXFED-27JAN"
    after = next_scheduled_meeting(SCHEDULE, as_of=datetime(2026, 9, 16, 19, tzinfo=UTC))
    assert after.release_at.date() == date(2026, 10, 28)


def test_ladder_collapses_to_cut_hold_hike_given_current_rate() -> None:
    market = market_cut_probability(LADDER_RECORD, current_upper=4.0, source_file="x.json")
    assert market.probability == pytest.approx(0.475)  # 0.005 + 0.47
    assert market.hold_probability == pytest.approx(0.51)
    assert market.hike_probability == pytest.approx(0.015)
    assert market.lower_bound == pytest.approx(0.46)
    assert market.upper_bound == pytest.approx(0.52)  # 0.01 + 0.01 + 0.01 + 0.01 + 0.48
    # If the rate were already 3.75, only the buckets strictly below count as a cut.
    lower = market_cut_probability(LADDER_RECORD, current_upper=3.75, source_file="x.json")
    assert lower.probability == pytest.approx(0.005)
    assert lower.hold_probability == pytest.approx(0.47)


def test_latest_record_is_read_from_committed_snapshots(tmp_path: Path) -> None:
    (tmp_path / "market_prices_20260908T020000Z.json").write_text(json.dumps([{**LADDER_RECORD, "observed_at": "old"}]))
    (tmp_path / "market_prices_20260908T024439Z.json").write_text(json.dumps([LADDER_RECORD]))
    (tmp_path / "market_prices_20260908T030000Z.json").write_text(
        json.dumps([{**LADDER_RECORD, "probabilities": {}, "rejected_reason": "wide"}])
    )
    found = latest_ladder_record(tmp_path, event_ticker="KXFED-26SEP")
    assert found is not None
    record, source = found
    assert source == "market_prices_20260908T024439Z.json"  # newest *priced* record wins
    assert record["observed_at"] == "2026-09-08T02:44:39+00:00"
    assert latest_ladder_record(tmp_path, event_ticker="KXFED-26OCT") is None


def test_live_snapshot_uses_today_as_vintage_and_refuses_future_vintage() -> None:
    months = [(2025 + (index + 7) // 12, (index + 7) % 12 + 1) for index in range(13)]
    cpi = [observation("CPIAUCNS", y, m, 320 + index) for index, (y, m) in enumerate(months)]
    unemployment = [observation("UNRATE", 2026, m, v) for m, v in [(4, 4.2), (5, 4.2), (6, 4.1), (7, 4.2)]]
    policy = [observation("DFEDTARU", 2026, 9, 4.0)]
    client = FakeAlfredClient({"CPIAUCNS": cpi, "UNRATE": unemployment, "DFEDTARU": policy})
    snapshot = build_feature_snapshot(client, meeting_date=date(2026, 9, 16), vintage_date=date(2026, 9, 8))
    assert snapshot.vintage_date == "2026-09-08" and snapshot.meeting_date == "2026-09-16"
    assert snapshot.policy_rate_upper == 4.0
    assert set(client.requested_vintages) == {date(2026, 9, 8)}
    with pytest.raises(ValueError, match="precede"):
        build_feature_snapshot(client, meeting_date=date(2026, 9, 16), vintage_date=date(2026, 9, 16))


def test_models_and_comparison_record_keep_signals_off() -> None:
    training = scheduled_meetings(load_fomc_history(ROOT / "data" / "fomc_meetings_2019_2024.csv"))
    training_snapshots = json.loads(
        (ROOT / "data" / "generated" / "fomc_feature_snapshots_2019_2024.json").read_text()
    )
    snapshot = HistoricalFeatureSnapshot(
        meeting_date="2026-09-16",
        vintage_date="2026-09-08",
        cpi_yoy_nsa=2.7,
        unemployment_rate=4.3,
        unemployment_change_3m=0.2,
        policy_rate_upper=4.0,
        source_series={"cpi_yoy_nsa": "CPIAUCNS", "unemployment_rate": "UNRATE", "policy_rate_upper": "DFEDTARU"},
    )
    heuristic, logistic = model_cut_probabilities(snapshot, training, training_snapshots)
    assert 0.0 < heuristic < 1.0 and 0.0 < logistic < 1.0
    market = market_cut_probability(LADDER_RECORD, current_upper=4.0, source_file="x.json")
    meeting = next_scheduled_meeting(SCHEDULE, as_of=NOW)
    record = build_comparison(
        as_of=NOW, meeting=meeting, snapshot=snapshot, heuristic_cut=heuristic,
        logistic_cut=logistic, training_size=len(training), market=market,
    )
    assert record.event_ticker == "KXFED-26SEP"
    assert record.logistic_edge == pytest.approx(logistic - 0.475)
    assert record.signal_eligible is False
    assert record.model_version == "fed-live-0.4-three-way-2015-nonzlb-uncalibrated"
    assert record.to_dict()["market"]["source_file"] == "x.json"


def test_live_vintage_uses_fred_chicago_clock_and_falls_back_on_500() -> None:
    import httpx

    from forecast_macro.snapshots import build_feature_snapshot_with_fallback, latest_safe_vintage

    # 04:05 UTC on Sep 8 is 23:05 on Sep 7 in Chicago: the vintage must be Sep 7.
    assert latest_safe_vintage(datetime(2026, 9, 8, 4, 5, tzinfo=UTC)) == date(2026, 9, 7)
    assert latest_safe_vintage(datetime(2026, 9, 8, 13, 40, tzinfo=UTC)) == date(2026, 9, 8)

    class RejectsTomorrow(FakeAlfredClient):
        def observations_as_of(self, series_id, *, vintage_date, observation_start, observation_end):
            if vintage_date >= date(2026, 9, 8):
                request = httpx.Request("GET", "https://api.stlouisfed.org/x")
                raise httpx.HTTPStatusError("500", request=request, response=httpx.Response(500, request=request))
            return super().observations_as_of(
                series_id, vintage_date=vintage_date, observation_start=observation_start, observation_end=observation_end
            )

    months = [(2025 + (index + 7) // 12, (index + 7) % 12 + 1) for index in range(13)]
    cpi = [observation("CPIAUCNS", y, m, 320 + index) for index, (y, m) in enumerate(months)]
    unemployment = [observation("UNRATE", 2026, m, v) for m, v in [(4, 4.2), (5, 4.2), (6, 4.1), (7, 4.2)]]
    policy = [observation("DFEDTARU", 2026, 9, 3.75)]
    client = RejectsTomorrow({"CPIAUCNS": cpi, "UNRATE": unemployment, "DFEDTARU": policy})
    snapshot = build_feature_snapshot_with_fallback(
        client, meeting_date=date(2026, 9, 16), as_of=datetime(2026, 9, 8, 13, 40, tzinfo=UTC)
    )
    assert snapshot.vintage_date == "2026-09-07"  # stepped back once after the 500
