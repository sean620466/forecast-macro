from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ReleasedValue:
    name: str
    value: float
    released_at: datetime
    vintage: str


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
    values = (inflation_yoy, unemployment_rate, unemployment_3m_ago, policy_rate)
    future = [item.name for item in values if item.released_at > forecast_at]
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
