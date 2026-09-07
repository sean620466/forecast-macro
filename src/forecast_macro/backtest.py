from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TimedRow:
    available_at: datetime
    value: float


@dataclass(frozen=True)
class TimeSplit:
    train_indices: tuple[int, ...]
    test_indices: tuple[int, ...]


def available_rows(rows: list[TimedRow], *, as_of: datetime) -> list[TimedRow]:
    """Return only information that was publicly available by the forecast cutoff."""
    return [row for row in rows if row.available_at <= as_of]


def expanding_window_splits(
    timestamps: list[datetime],
    *,
    minimum_train_size: int,
    test_size: int = 1,
) -> list[TimeSplit]:
    if timestamps != sorted(timestamps):
        raise ValueError("timestamps must be sorted oldest to newest")
    if minimum_train_size < 1 or test_size < 1:
        raise ValueError("split sizes must be positive")
    if len(timestamps) < minimum_train_size + test_size:
        return []

    splits: list[TimeSplit] = []
    test_start = minimum_train_size
    while test_start + test_size <= len(timestamps):
        train = tuple(range(test_start))
        test = tuple(range(test_start, test_start + test_size))
        splits.append(TimeSplit(train_indices=train, test_indices=test))
        test_start += test_size
    return splits
