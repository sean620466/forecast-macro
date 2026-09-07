from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from forecast_macro.data.alfred import VintageObservation


@dataclass(frozen=True)
class ReleasedValue:
    name: str
    value: float
    released_at: datetime
    vintage: str
    vintage_verified: bool = False

    def __post_init__(self) -> None:
        if self.released_at.tzinfo is None:
            raise ValueError("released_at must be timezone-aware")


def released_value_from_vintage(
    observation: VintageObservation,
    *,
    name: str,
    release_time: time,
    timezone: str = "America/New_York",
) -> ReleasedValue:
    """Promote an ALFRED vintage date using an explicit source release-time rule."""
    if release_time.tzinfo is not None:
        raise ValueError("release_time must be a local wall-clock time")
    released_at = datetime.combine(
        observation.realtime_start,
        release_time,
        tzinfo=ZoneInfo(timezone),
    )
    return ReleasedValue(
        name=name,
        value=observation.value,
        released_at=released_at,
        vintage=observation.realtime_start.isoformat(),
        vintage_verified=True,
    )


@dataclass(frozen=True)
class FomcFeatureSnapshot:
    forecast_at: datetime
    inflation_yoy: float
    unemployment_rate: float
    unemployment_change_3m: float
    policy_rate: float
    vintages: dict[str, str]


def build_fomc_snapshot(
    *,
    forecast_at: datetime,
    inflation_yoy: ReleasedValue,
    unemployment_rate: ReleasedValue,
    unemployment_3m_ago: ReleasedValue,
    policy_rate: ReleasedValue,
) -> FomcFeatureSnapshot:
    if forecast_at.tzinfo is None:
        raise ValueError("forecast_at must be timezone-aware")
    values = (inflation_yoy, unemployment_rate, unemployment_3m_ago, policy_rate)
    if not all(item.vintage_verified for item in values):
        raise ValueError("all features must come from verified vintage data")
    if unemployment_rate.vintage != unemployment_3m_ago.vintage:
        raise ValueError("unemployment vintages must match")
    future = [item.name for item in values if item.released_at >= forecast_at]
    if future:
        raise ValueError(f"features released after forecast cutoff: {', '.join(future)}")

    return FomcFeatureSnapshot(
        forecast_at=forecast_at,
        inflation_yoy=inflation_yoy.value,
        unemployment_rate=unemployment_rate.value,
        unemployment_change_3m=unemployment_rate.value - unemployment_3m_ago.value,
        policy_rate=policy_rate.value,
        vintages={item.name: item.vintage for item in values},
    )
