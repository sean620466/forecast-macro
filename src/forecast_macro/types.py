from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Observation:
    series_id: str
    value: float
    observed_at: datetime
    released_at: datetime | None = None


@dataclass(frozen=True)
class Probability:
    outcome: str
    probability: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError("probability must be between 0 and 1")


@dataclass(frozen=True)
class MarketSignal:
    outcome: str
    model_probability: float
    market_probability: float
    edge: float
    should_display: bool
