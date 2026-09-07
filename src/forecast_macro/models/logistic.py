from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean, pstdev


@dataclass(frozen=True)
class LogisticModel:
    means: tuple[float, ...]
    scales: tuple[float, ...]
    intercept: float
    coefficients: tuple[float, ...]

    def predict(self, features: tuple[float, ...]) -> float:
        if len(features) != len(self.coefficients):
            raise ValueError("feature count does not match fitted model")
        standardized = [
            (value - mean) / scale
            for value, mean, scale in zip(features, self.means, self.scales, strict=True)
        ]
        score = self.intercept + sum(
            coefficient * value
            for coefficient, value in zip(self.coefficients, standardized, strict=True)
        )
        if score >= 0:
            return 1.0 / (1.0 + math.exp(-score))
        exp_score = math.exp(score)
        return exp_score / (1.0 + exp_score)


def fit_logistic(
    features: list[tuple[float, ...]],
    outcomes: list[int],
    *,
    ridge_strength: float = 1.0,
    learning_rate: float = 0.05,
    iterations: int = 2_000,
) -> LogisticModel:
    """Fit a small deterministic ridge-logistic model without external ML dependencies."""
    if not features or len(features) != len(outcomes):
        raise ValueError("features and outcomes must be non-empty and aligned")
    width = len(features[0])
    if width == 0 or any(len(row) != width for row in features):
        raise ValueError("feature rows must have a consistent positive width")
    if any(outcome not in (0, 1) for outcome in outcomes):
        raise ValueError("outcomes must be binary")
    if ridge_strength < 0 or learning_rate <= 0 or iterations < 1:
        raise ValueError("invalid optimizer parameters")

    columns = list(zip(*features, strict=True))
    means = tuple(fmean(column) for column in columns)
    scales = tuple(max(pstdev(column), 1e-9) for column in columns)
    matrix = [
        tuple(
            (value - mean) / scale
            for value, mean, scale in zip(row, means, scales, strict=True)
        )
        for row in features
    ]
    # Smoothed empirical log-odds gives the optimizer a stable rare-event starting point.
    positives = sum(outcomes)
    intercept = math.log((positives + 1) / (len(outcomes) - positives + 1))
    coefficients = [0.0] * width
    sample_count = len(outcomes)

    for _ in range(iterations):
        intercept_gradient = 0.0
        gradients = [0.0] * width
        for row, outcome in zip(matrix, outcomes, strict=True):
            score = intercept + sum(
                coefficient * value
                for coefficient, value in zip(coefficients, row, strict=True)
            )
            probability = 1.0 / (1.0 + math.exp(-max(min(score, 35.0), -35.0)))
            error = probability - outcome
            intercept_gradient += error
            for index, value in enumerate(row):
                gradients[index] += error * value
        intercept -= learning_rate * intercept_gradient / sample_count
        for index in range(width):
            regularized = gradients[index] / sample_count + ridge_strength * coefficients[index]
            coefficients[index] -= learning_rate * regularized

    return LogisticModel(means, scales, intercept, tuple(coefficients))
