from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class TimedRow:
    available_at: datetime
    value: float


@dataclass(frozen=True)
class TimeSplit:
    train_indices: tuple[int, ...]
    test_indices: tuple[int, ...]


@dataclass(frozen=True)
class ForecastEvent:
    forecast_at: datetime
    outcome_at: datetime

    def __post_init__(self) -> None:
        if self.forecast_at.tzinfo is None or self.outcome_at.tzinfo is None:
            raise ValueError("event timestamps must be timezone-aware")
        if self.forecast_at >= self.outcome_at:
            raise ValueError("forecast_at must precede outcome_at")


def available_rows(rows: list[TimedRow], *, as_of: datetime) -> list[TimedRow]:
    """Return only information that was publicly available by the forecast cutoff."""
    if as_of.tzinfo is None or any(row.available_at.tzinfo is None for row in rows):
        raise ValueError("timestamps must be timezone-aware")
    return [row for row in rows if row.available_at < as_of]


def expanding_window_splits(
    timestamps: list[datetime],
    *,
    minimum_train_size: int,
    test_size: int = 1,
    include_partial_test: bool = False,
) -> list[TimeSplit]:
    if timestamps != sorted(timestamps):
        raise ValueError("timestamps must be sorted oldest to newest")
    if minimum_train_size < 1 or test_size < 1:
        raise ValueError("split sizes must be positive")
    if len(timestamps) < minimum_train_size + test_size:
        return []

    splits: list[TimeSplit] = []
    test_start = minimum_train_size
    while test_start < len(timestamps):
        test_end = min(test_start + test_size, len(timestamps))
        if test_end - test_start < test_size and not include_partial_test:
            break
        train = tuple(range(test_start))
        test = tuple(range(test_start, test_end))
        splits.append(TimeSplit(train_indices=train, test_indices=test))
        test_start = test_end
    return splits


def purged_expanding_window_splits(
    events: list[ForecastEvent],
    *,
    minimum_train_size: int,
    test_size: int = 1,
    embargo: timedelta = timedelta(0),
    include_partial_test: bool = False,
) -> list[TimeSplit]:
    if embargo < timedelta(0):
        raise ValueError("embargo must be non-negative")
    if minimum_train_size < 1 or test_size < 1:
        raise ValueError("split sizes must be positive")
    if [event.forecast_at for event in events] != sorted(event.forecast_at for event in events):
        raise ValueError("events must be sorted by forecast_at")

    splits: list[TimeSplit] = []
    test_start = minimum_train_size
    while test_start < len(events):
        test_end = min(test_start + test_size, len(events))
        if test_end - test_start < test_size and not include_partial_test:
            break
        cutoff = events[test_start].forecast_at - embargo
        train = tuple(i for i in range(test_start) if events[i].outcome_at < cutoff)
        if len(train) >= minimum_train_size:
            splits.append(TimeSplit(train, tuple(range(test_start, test_end))))
        test_start = test_end
    return splits
