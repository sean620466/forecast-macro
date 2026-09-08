from datetime import UTC, date, datetime

import pytest

from forecast_macro.data.alfred import VintageObservation
from forecast_macro.datasets import HistoricalFomcRow
from forecast_macro.fomc import RateDecision
from forecast_macro.snapshots import build_historical_snapshot


def observation(series: str, year: int, month: int, value: float) -> VintageObservation:
    vintage = date(2024, 9, 17)
    return VintageObservation(
        series_id=series,
        value=value,
        observed_at=date(year, month, 1),
        realtime_start=vintage,
        realtime_end=vintage,
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class FakeAlfredClient:
    def __init__(self, series):
        self.series = series
        self.requested_vintages = []

    def observations_as_of(self, series_id, *, vintage_date, observation_start, observation_end):
        self.requested_vintages.append(vintage_date)
        return self.series[series_id]


def test_build_snapshot_uses_prior_day_and_calculates_features():
    months = [(2023 + (index + 8) // 12, (index + 8) % 12 + 1) for index in range(13)]
    cpi = [observation("CPIAUCNS", year, month, 300 + index) for index, (year, month) in enumerate(months)]
    unemployment = [
        observation("UNRATE", 2024, month, value)
        for month, value in [(5, 4.0), (6, 4.1), (7, 4.2), (8, 4.3)]
    ]
    policy = [observation("DFEDTARU", 2024, 9, 5.5)]
    client = FakeAlfredClient({"CPIAUCNS": cpi, "UNRATE": unemployment, "DFEDTARU": policy})
    meeting = HistoricalFomcRow(
        meeting_at=datetime(2024, 9, 18, 14, tzinfo=UTC),
        upper_before=5.5,
        upper_after=5.0,
        change_bps=-50,
        decision=RateDecision.CUT,
        source="https://www.federalreserve.gov/test",
    )
    snapshot = build_historical_snapshot(client, meeting)
    assert snapshot.vintage_date == "2024-09-17"
    assert snapshot.unemployment_change_3m == pytest.approx(0.3)
    assert snapshot.policy_rate_upper == 5.5
    assert snapshot.cpi_yoy_nsa == pytest.approx(4.0)
    assert set(client.requested_vintages) == {date(2024, 9, 17)}


def test_snapshot_rejects_missing_months():
    cpi = [observation("CPIAUCNS", 2024, 1, 300.0)] * 13
    unemployment = [observation("UNRATE", 2024, 1, 4.0)] * 4
    policy = [observation("DFEDTARU", 2024, 1, 5.5)]
    client = FakeAlfredClient({"CPIAUCNS": cpi, "UNRATE": unemployment, "DFEDTARU": policy})
    meeting = HistoricalFomcRow(
        datetime(2024, 2, 1, tzinfo=UTC),
        5.5,
        5.5,
        0,
        RateDecision.HOLD,
        "https://www.federalreserve.gov/test",
    )
    with pytest.raises(ValueError, match="missing the 2023-01 observation"):
        build_historical_snapshot(client, meeting)


def test_unpublished_middle_month_is_tolerated_and_recorded():
    # BLS never published October 2025 CPI or unemployment after the 2025 shutdown.
    months = [(2025, m) for m in range(7, 13)] + [(2026, m) for m in range(1, 8)]
    cpi = [
        observation("CPIAUCNS", y, m, 320 + index)
        for index, (y, m) in enumerate(months)
        if (y, m) != (2025, 10)
    ]
    unemployment = [
        observation("UNRATE", 2026, m, v) for m, v in [(4, 4.3), (5, 4.3), (6, 4.2), (7, 4.1)]
    ]
    policy = [observation("DFEDTARU", 2026, 9, 3.75)]
    client = FakeAlfredClient({"CPIAUCNS": cpi, "UNRATE": unemployment, "DFEDTARU": policy})
    from forecast_macro.snapshots import build_feature_snapshot

    snapshot = build_feature_snapshot(client, meeting_date=date(2026, 9, 16), vintage_date=date(2026, 9, 7))
    assert snapshot.cpi_yoy_nsa == pytest.approx((332 / 320 - 1) * 100)  # Jul 2026 vs Jul 2025
    assert snapshot.unemployment_change_3m == pytest.approx(-0.2)
    assert snapshot.data_gaps == {"CPIAUCNS": ["2025-10"]}
    assert "data_gaps" in snapshot.to_dict()


def test_snapshot_records_input_provenance():
    from forecast_macro.snapshots import SNAPSHOT_BUILDER_VERSION, build_feature_snapshot

    months = [(2025 + (index + 7) // 12, (index + 7) % 12 + 1) for index in range(13)]
    cpi = [observation("CPIAUCNS", y, m, 320 + index) for index, (y, m) in enumerate(months)]
    unemployment = [observation("UNRATE", 2026, m, v) for m, v in [(4, 4.3), (5, 4.3), (6, 4.2), (7, 4.1)]]
    policy = [observation("DFEDTARU", 2026, 9, 3.75)]
    client = FakeAlfredClient({"CPIAUCNS": cpi, "UNRATE": unemployment, "DFEDTARU": policy})
    snapshot = build_feature_snapshot(
        client, meeting_date=date(2026, 9, 16), vintage_date=date(2026, 9, 7), build_commit="abc123"
    )
    assert set(snapshot.inputs) == {
        "cpi_latest", "cpi_base_12m", "unemployment_latest", "unemployment_base_3m", "policy_rate_upper"
    }
    assert snapshot.inputs["cpi_latest"]["observed_at"] == "2026-08-01"
    assert snapshot.inputs["cpi_base_12m"]["observed_at"] == "2025-08-01"
    assert snapshot.inputs["unemployment_base_3m"]["observed_at"] == "2026-04-01"
    assert snapshot.inputs["policy_rate_upper"]["realtime_start"] == "2024-09-17"  # fake vintage
    assert snapshot.provenance["builder_version"] == SNAPSHOT_BUILDER_VERSION
    assert snapshot.provenance["build_commit"] == "abc123"
    assert "inputs" in snapshot.to_dict() and "provenance" in snapshot.to_dict()


def test_first_publication_dates_come_from_the_full_vintage_history():
    from forecast_macro.snapshots import build_feature_snapshot

    class WithHistory(FakeAlfredClient):
        def __init__(self, series):
            super().__init__(series)
            self.first_release_queries = []

        def first_release_date(self, series_id, observed_at):
            self.first_release_queries.append((series_id, observed_at))
            return {"CPIAUCNS": date(2026, 8, 12), "UNRATE": date(2026, 9, 4), "DFEDTARU": date(2025, 12, 11)}[series_id]

    months = [(2025 + (index + 7) // 12, (index + 7) % 12 + 1) for index in range(13)]
    cpi = [observation("CPIAUCNS", y, m, 320 + index) for index, (y, m) in enumerate(months)]
    unemployment = [observation("UNRATE", 2026, m, v) for m, v in [(5, 4.3), (6, 4.2), (7, 4.1), (8, 4.1)]]
    policy = [observation("DFEDTARU", 2026, 9, 3.75)]
    client = WithHistory({"CPIAUCNS": cpi, "UNRATE": unemployment, "DFEDTARU": policy})
    snapshot = build_feature_snapshot(
        client, meeting_date=date(2026, 9, 16), vintage_date=date(2026, 9, 7), first_release_dates=True
    )
    assert snapshot.inputs["cpi_latest"]["first_published_on"] == "2026-08-12"
    assert snapshot.inputs["unemployment_latest"]["first_published_on"] == "2026-09-04"
    assert "first_published_on" not in snapshot.inputs["cpi_base_12m"]
    assert len(client.first_release_queries) == 5  # 3 first-release + 2 next-release (D-017)
    assert snapshot.inputs["cpi_latest"]["next_release_on"] == "2026-08-12"
    assert snapshot.same_day_release is False and snapshot.same_day_release_series == []
    plain = build_feature_snapshot(client, meeting_date=date(2026, 9, 16), vintage_date=date(2026, 9, 7))
    assert "first_published_on" not in plain.inputs["cpi_latest"]
