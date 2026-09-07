from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from itertools import pairwise

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

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _latest(rows: list[VintageObservation], *, on_or_before: date) -> VintageObservation:
    eligible = [row for row in rows if row.observed_at <= on_or_before]
    if not eligible:
        raise ValueError(f"no observation available by {on_or_before}")
    return max(eligible, key=lambda row: row.observed_at)


def _monthly_tail(
    rows: list[VintageObservation], *, on_or_before: date, count: int
) -> list[VintageObservation]:
    eligible = sorted(
        (row for row in rows if row.observed_at <= on_or_before),
        key=lambda row: row.observed_at,
    )
    if len(eligible) < count:
        raise ValueError(f"need {count} observations by {on_or_before}")
    tail = eligible[-count:]
    months = [row.observed_at.year * 12 + row.observed_at.month for row in tail]
    if any(current - previous != 1 for previous, current in pairwise(months)):
        raise ValueError("monthly snapshot contains a gap")
    return tail


def build_historical_snapshot(
    client: AlfredClient,
    meeting: HistoricalFomcRow,
) -> HistoricalFeatureSnapshot:
    # A prior-calendar-day cutoff avoids ambiguous same-day release timestamps.
    vintage_date = meeting.meeting_at.date() - timedelta(days=1)
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

    cpi = _monthly_tail(series["CPIAUCNS"], on_or_before=vintage_date, count=13)
    unemployment = _monthly_tail(series["UNRATE"], on_or_before=vintage_date, count=4)
    policy_rate = _latest(series["DFEDTARU"], on_or_before=vintage_date)
    return HistoricalFeatureSnapshot(
        meeting_date=meeting.meeting_at.date().isoformat(),
        vintage_date=vintage_date.isoformat(),
        cpi_yoy_nsa=percent_change(cpi[-1].value, cpi[0].value),
        unemployment_rate=unemployment[-1].value,
        unemployment_change_3m=unemployment[-1].value - unemployment[0].value,
        policy_rate_upper=policy_rate.value,
        source_series={
            "cpi_yoy_nsa": "CPIAUCNS",
            "unemployment_rate": "UNRATE",
            "policy_rate_upper": "DFEDTARU",
        },
    )
