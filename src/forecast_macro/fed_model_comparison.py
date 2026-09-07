from __future__ import annotations

from dataclasses import asdict, dataclass

from forecast_macro.datasets import HistoricalFomcRow
from forecast_macro.evaluation import ForecastRecord, brier_score, expected_calibration_error
from forecast_macro.fomc import RateDecision
from forecast_macro.models.logistic import fit_logistic


@dataclass(frozen=True)
class WalkForwardReport:
    evaluated_meetings: int
    actual_cuts: int
    model_brier: float
    sequential_climatology_brier: float
    brier_skill_vs_climatology: float
    calibration_ece: float
    minimum_sample_required: int
    climatology_gate_passed: bool
    market_baseline_available: bool
    signal_eligible: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _features(snapshot: dict[str, object]) -> tuple[float, ...]:
    return (
        float(snapshot["cpi_yoy_nsa"]),
        float(snapshot["unemployment_rate"]),
        float(snapshot["unemployment_change_3m"]),
        float(snapshot["policy_rate_upper"]),
    )


def run_walk_forward_logistic(
    meetings: list[HistoricalFomcRow],
    snapshots: list[dict[str, object]],
    *,
    warmup: int = 8,
    minimum_sample_required: int = 30,
) -> WalkForwardReport:
    """Refit only on prior decisions before predicting each next meeting."""
    if warmup < 4 or warmup >= len(meetings):
        raise ValueError("warmup must be at least four and leave an evaluation row")
    by_date = {str(row["meeting_date"]): row for row in snapshots}
    if len(by_date) != len(snapshots):
        raise ValueError("snapshot meeting dates must be unique")

    model_records: list[ForecastRecord] = []
    baseline_records: list[ForecastRecord] = []
    for index in range(warmup, len(meetings)):
        training = meetings[:index]
        training_snapshots = [by_date[row.meeting_at.date().isoformat()] for row in training]
        model = fit_logistic(
            [_features(snapshot) for snapshot in training_snapshots],
            [int(row.decision is RateDecision.CUT) for row in training],
        )
        meeting = meetings[index]
        snapshot = by_date[meeting.meeting_at.date().isoformat()]
        probability = model.predict(_features(snapshot))
        outcome = int(meeting.decision is RateDecision.CUT)
        prior_cuts = sum(row.decision is RateDecision.CUT for row in training)
        baseline = (prior_cuts + 1) / (len(training) + 2)
        forecast_at = meeting.meeting_at.replace(hour=0, minute=0, second=0, microsecond=0)
        model_records.append(ForecastRecord(forecast_at, meeting.meeting_at, probability, outcome))
        baseline_records.append(ForecastRecord(forecast_at, meeting.meeting_at, baseline, outcome))

    model_brier = brier_score(model_records)
    baseline_brier = brier_score(baseline_records)
    evaluated = len(model_records)
    return WalkForwardReport(
        evaluated_meetings=evaluated,
        actual_cuts=sum(record.outcome for record in model_records),
        model_brier=model_brier,
        sequential_climatology_brier=baseline_brier,
        brier_skill_vs_climatology=1.0 - model_brier / baseline_brier,
        calibration_ece=expected_calibration_error(model_records, bins=5),
        minimum_sample_required=minimum_sample_required,
        climatology_gate_passed=evaluated >= minimum_sample_required
        and model_brier < baseline_brier,
        market_baseline_available=False,
        # D-007 requires positive out-of-sample skill against market prices.
        signal_eligible=False,
    )
