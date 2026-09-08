from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta

from forecast_macro.data.alfred import AlfredClient, VintageObservation
from forecast_macro.datasets import HistoricalFomcRow
from forecast_macro.transforms import percent_change


@dataclass(frozen=True)
class HistoricalFeatureSnapshot:
    meeting_date: str
    vintage_date: str
    cpi_yoy_nsa: float
    unemployment_rate: float
    unemployment_change_3m: float
    policy_rate_upper: float
    source_series: dict[str, str]
    # Months with no published observation between a feature's two endpoints (for example
    # October 2025, which BLS never published after the 2025 shutdown). Recorded, not hidden.
    data_gaps: dict[str, list[str]] = field(default_factory=dict)
    # R4-M3 reproducibility: every input observation with its observation month, the ALFRED
    # real-time start (first date the value was visible), and the fetch time; plus the build.
    inputs: dict[str, dict[str, object]] = field(default_factory=dict)
    provenance: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _latest(rows: list[VintageObservation], *, on_or_before: date) -> VintageObservation:
    eligible = [row for row in rows if row.observed_at <= on_or_before]
    if not eligible:
        raise ValueError(f"no observation available by {on_or_before}")
    return max(eligible, key=lambda row: row.observed_at)


def _month_index(value: date) -> int:
    return value.year * 12 + value.month


def _endpoints(
    rows: list[VintageObservation], *, on_or_before: date, months_apart: int
) -> tuple[VintageObservation, VintageObservation, list[str]]:
    """Latest observation by the cutoff and the one exactly months_apart earlier.

    A change over N months only needs its two endpoints. Months in between that were never
    published (BLS skipped October 2025 after the shutdown) do not invalidate the change,
    but they are returned so the snapshot can record them. A missing endpoint is an error.
    """
    eligible = {
        _month_index(row.observed_at): row for row in rows if row.observed_at <= on_or_before
    }
    if not eligible:
        raise ValueError(f"no observation available by {on_or_before}")
    latest_index = max(eligible)
    older_index = latest_index - months_apart
    if older_index not in eligible:
        year, month = divmod(older_index - 1, 12)
        raise ValueError(
            f"monthly snapshot is missing the {year}-{month + 1:02d} observation needed for a "
            f"{months_apart}-month change"
        )
    gaps = [
        f"{divmod(index - 1, 12)[0]}-{divmod(index - 1, 12)[1] + 1:02d}"
        for index in range(older_index + 1, latest_index)
        if index not in eligible
    ]
    return eligible[older_index], eligible[latest_index], gaps


def build_historical_snapshot(
    client: AlfredClient,
    meeting: HistoricalFomcRow,
) -> HistoricalFeatureSnapshot:
    # A prior-calendar-day cutoff avoids ambiguous same-day release timestamps.
    vintage_date = meeting.meeting_at.date() - timedelta(days=1)
    return build_feature_snapshot(
        client, meeting_date=meeting.meeting_at.date(), vintage_date=vintage_date
    )


SNAPSHOT_BUILDER_VERSION = "fomc-feature-snapshot-0.2"


def _describe(row: VintageObservation) -> dict[str, object]:
    return {
        "series_id": row.series_id,
        "observed_at": row.observed_at.isoformat(),
        "value": row.value,
        "realtime_start": row.realtime_start.isoformat(),
        "fetched_at": row.fetched_at.isoformat(),
    }


def build_feature_snapshot(
    client: AlfredClient,
    *,
    meeting_date: date,
    vintage_date: date,
    build_commit: str = "",
) -> HistoricalFeatureSnapshot:
    """Point-in-time features for a meeting as they were visible on vintage_date.

    Used both for the historical backtest (vintage = day before the meeting) and for the live
    comparison (vintage = today, meeting = next scheduled decision).
    """
    if vintage_date >= meeting_date:
        raise ValueError("vintage_date must precede the meeting date")
    start = date(vintage_date.year - 2, 1, 1)
    series = {
        series_id: client.observations_as_of(
            series_id,
            vintage_date=vintage_date,
            observation_start=start,
            observation_end=vintage_date,
        )
        for series_id in ("CPIAUCNS", "UNRATE", "DFEDTARU")
    }

    cpi_old, cpi_new, cpi_gaps = _endpoints(
        series["CPIAUCNS"], on_or_before=vintage_date, months_apart=12
    )
    unemp_old, unemp_new, unemp_gaps = _endpoints(
        series["UNRATE"], on_or_before=vintage_date, months_apart=3
    )
    policy_rate = _latest(series["DFEDTARU"], on_or_before=vintage_date)
    gaps = {name: months for name, months in (("CPIAUCNS", cpi_gaps), ("UNRATE", unemp_gaps)) if months}
    return HistoricalFeatureSnapshot(
        meeting_date=meeting_date.isoformat(),
        vintage_date=vintage_date.isoformat(),
        cpi_yoy_nsa=percent_change(cpi_new.value, cpi_old.value),
        unemployment_rate=unemp_new.value,
        unemployment_change_3m=unemp_new.value - unemp_old.value,
        policy_rate_upper=policy_rate.value,
        source_series={
            "cpi_yoy_nsa": "CPIAUCNS",
            "unemployment_rate": "UNRATE",
            "policy_rate_upper": "DFEDTARU",
        },
        data_gaps=gaps,
        inputs={
            "cpi_latest": _describe(cpi_new),
            "cpi_base_12m": _describe(cpi_old),
            "unemployment_latest": _describe(unemp_new),
            "unemployment_base_3m": _describe(unemp_old),
            "policy_rate_upper": _describe(policy_rate),
        },
        provenance={
            "builder_version": SNAPSHOT_BUILDER_VERSION,
            "built_at": datetime.now(UTC).isoformat(),
            "build_commit": build_commit,
        },
    )
