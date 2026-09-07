from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ForecastRecord:
    forecast_at: datetime
    outcome_at: datetime
    probability: float
    outcome: int

    def __post_init__(self) -> None:
        if self.forecast_at.tzinfo is None or self.outcome_at.tzinfo is None:
            raise ValueError("forecast and outcome timestamps must be timezone-aware")
        if self.forecast_at >= self.outcome_at:
            raise ValueError("forecast_at must be earlier than outcome_at")
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError("probability must be between 0 and 1")
        if self.outcome not in (0, 1):
            raise ValueError("outcome must be 0 or 1")


@dataclass(frozen=True)
class CalibrationBin:
    lower: float
    upper: float
    count: int
    mean_probability: float
    observed_frequency: float


def brier_score(records: list[ForecastRecord]) -> float:
    if not records:
        raise ValueError("at least one forecast is required")
    return sum((row.probability - row.outcome) ** 2 for row in records) / len(records)


def calibration_table(
    records: list[ForecastRecord], *, bins: int = 10
) -> list[CalibrationBin]:
    if not records:
        raise ValueError("at least one forecast is required")
    if bins < 2:
        raise ValueError("bins must be at least 2")

    result: list[CalibrationBin] = []
    width = 1.0 / bins
    grouped: list[list[ForecastRecord]] = [[] for _ in range(bins)]
    for row in records:
        index = min(bins - 1, math.floor(row.probability * bins + 1e-12))
        grouped[index].append(row)
    for index in range(bins):
        lower = index * width
        upper = (index + 1) * width
        members = grouped[index]
        if not members:
            continue
        result.append(
            CalibrationBin(
                lower=lower,
                upper=upper,
                count=len(members),
                mean_probability=sum(row.probability for row in members) / len(members),
                observed_frequency=sum(row.outcome for row in members) / len(members),
            )
        )
    return result


def expected_calibration_error(records: list[ForecastRecord], *, bins: int = 10) -> float:
    table = calibration_table(records, bins=bins)
    total = len(records)
    return sum(
        row.count / total * abs(row.mean_probability - row.observed_frequency)
        for row in table
    )


def climatology_probability(records: list[ForecastRecord]) -> float:
    if not records:
        raise ValueError("at least one forecast is required")
    return sum(row.outcome for row in records) / len(records)


def brier_skill_score(model_score: float, baseline_score: float) -> float:
    if not math.isfinite(model_score) or not math.isfinite(baseline_score):
        raise ValueError("scores must be finite")
    if baseline_score <= 0:
        raise ValueError("baseline_score must be positive")
    return 1.0 - model_score / baseline_score
