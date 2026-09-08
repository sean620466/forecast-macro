from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, time

from forecast_macro.datasets import HistoricalFomcRow
from forecast_macro.evaluation import ForecastRecord, brier_score, expected_calibration_error
from forecast_macro.fomc import RateDecision
from forecast_macro.models.fed import (
    PROBABILITY_EPSILON,
    ZLB_UPPER_BOUND,
    apply_cut_feasibility,
    split_remainder,
)
from forecast_macro.models.logistic import LogisticModel, fit_logistic


@dataclass(frozen=True)
class WalkForwardReport:
    evaluated_meetings: int
    non_zlb_evaluated_meetings: int
    actual_cuts: int
    model_brier: float
    sequential_climatology_brier: float
    always_hold_brier: float
    # Ablation: the same walk-forward fit with every coefficient removed, keeping only the
    # refitted intercept and the D-011 ZLB mask. If the full model is not clearly better
    # than this, the features are not contributing.
    intercept_only_brier: float
    brier_skill_vs_climatology: float
    brier_skill_vs_always_hold: float | None
    brier_skill_vs_intercept_only: float
    # Non-ZLB subset: meetings where the target upper bound exceeds 0.25%. D-013 counts
    # only these toward the research sample, and D-011 makes ZLB rows trivially correct.
    non_zlb_model_brier: float | None
    non_zlb_climatology_brier: float | None
    non_zlb_always_hold_brier: float | None
    non_zlb_brier_skill_vs_climatology: float | None
    calibration_ece: float
    minimum_sample_required: int
    climatology_gate_passed: bool
    market_baseline_available: bool
    signal_eligible: bool
    # D-016 three-way metrics (cut component identical to the binary metrics above).
    three_way_brier: float = 0.0
    three_way_climatology_brier: float = 0.0
    hold_brier: float = 0.0
    hike_brier: float = 0.0
    actual_hikes: int = 0
    # Per-meeting record (task 39) so sub-period comparisons between training ranges can be
    # made from the checked-in report instead of re-running the fit.
    predictions: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _features(snapshot: dict[str, object]) -> tuple[float, ...]:
    return (
        float(snapshot["cpi_yoy_nsa"]),
        float(snapshot["unemployment_rate"]),
        float(snapshot["unemployment_change_3m"]),
        float(snapshot["policy_rate_upper"]),
    )


def fit_hike_given_no_cut(
    training: list[HistoricalFomcRow], training_snapshots: list[dict[str, object]]
) -> LogisticModel | None:
    """Hike-vs-hold model fitted on the meetings that were not cuts (D-016, stage one)."""
    by_date = {str(row["meeting_date"]): row for row in training_snapshots}
    rows = [row for row in training if row.decision is not RateDecision.CUT]
    if len(rows) < 4:
        return None
    return fit_logistic(
        [_features(by_date[row.meeting_at.date().isoformat()]) for row in rows],
        [int(row.decision is RateDecision.HIKE) for row in rows],
    )


def hike_probability_given_no_cut(
    model: LogisticModel | None, features: tuple[float, ...]
) -> float:
    if model is None:
        return PROBABILITY_EPSILON
    return min(max(model.predict(features), PROBABILITY_EPSILON), 1.0 - PROBABILITY_EPSILON)


def _skill(model: float, baseline: float) -> float | None:
    """Brier skill score, or None when the baseline is perfect and the ratio is undefined."""
    if baseline <= 0.0:
        return None
    return 1.0 - model / baseline


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


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
    missing = [
        row.meeting_at.date().isoformat()
        for row in meetings
        if row.meeting_at.date().isoformat() not in by_date
    ]
    if missing:
        raise ValueError(f"missing snapshots: {', '.join(missing)}")
    for row in meetings:
        snapshot = by_date[row.meeting_at.date().isoformat()]
        if abs(float(snapshot["policy_rate_upper"]) - row.upper_before) > 1e-9:
            raise ValueError(f"policy-rate snapshot mismatch for {row.meeting_at.date()}")

    model_records: list[ForecastRecord] = []
    baseline_records: list[ForecastRecord] = []
    always_hold_records: list[ForecastRecord] = []
    intercept_records: list[ForecastRecord] = []
    zlb_flags: list[bool] = []
    three_way_errors: list[float] = []
    three_way_baseline_errors: list[float] = []
    hold_errors: list[float] = []
    hike_errors: list[float] = []
    actual_hikes = 0
    predictions: list[dict[str, object]] = []
    for index in range(warmup, len(meetings)):
        training = meetings[:index]
        training_snapshots = [by_date[row.meeting_at.date().isoformat()] for row in training]
        model = fit_logistic(
            [_features(snapshot) for snapshot in training_snapshots],
            [int(row.decision is RateDecision.CUT) for row in training],
        )
        hike_model = fit_hike_given_no_cut(training, training_snapshots)
        meeting = meetings[index]
        snapshot = by_date[meeting.meeting_at.date().isoformat()]
        policy_rate = float(snapshot["policy_rate_upper"])
        probability = apply_cut_feasibility(
            model.predict(_features(snapshot)), policy_rate=policy_rate
        )
        _, hold_probability, hike_probability = split_remainder(
            probability, hike_probability_given_no_cut(hike_model, _features(snapshot))
        )
        intercept_only = apply_cut_feasibility(_sigmoid(model.intercept), policy_rate=policy_rate)
        outcome = int(meeting.decision is RateDecision.CUT)
        is_hike = int(meeting.decision is RateDecision.HIKE)
        is_hold = int(meeting.decision is RateDecision.HOLD)
        actual_hikes += is_hike
        prior_cuts = sum(row.decision is RateDecision.CUT for row in training)
        prior_hikes = sum(row.decision is RateDecision.HIKE for row in training)
        baseline = (prior_cuts + 1) / (len(training) + 2)
        baseline_hike = (prior_hikes + 1) / (len(training) + 3)
        baseline_hold = max(0.0, 1.0 - baseline - baseline_hike)
        three_way_errors.append(
            (probability - outcome) ** 2
            + (hold_probability - is_hold) ** 2
            + (hike_probability - is_hike) ** 2
        )
        three_way_baseline_errors.append(
            (baseline - outcome) ** 2 + (baseline_hold - is_hold) ** 2 + (baseline_hike - is_hike) ** 2
        )
        hold_errors.append((hold_probability - is_hold) ** 2)
        hike_errors.append((hike_probability - is_hike) ** 2)
        # Same information cutoff as fed_backtest: end of the prior-day vintage.
        forecast_at = datetime.combine(
            datetime.fromisoformat(str(snapshot["vintage_date"])).date(),
            time(23, 59),
            tzinfo=UTC,
        )
        model_records.append(ForecastRecord(forecast_at, meeting.meeting_at, probability, outcome))
        baseline_records.append(ForecastRecord(forecast_at, meeting.meeting_at, baseline, outcome))
        always_hold_records.append(ForecastRecord(forecast_at, meeting.meeting_at, 0.0, outcome))
        intercept_records.append(
            ForecastRecord(forecast_at, meeting.meeting_at, intercept_only, outcome)
        )
        zlb_flags.append(policy_rate <= ZLB_UPPER_BOUND)
        predictions.append(
            {
                "meeting_date": meeting.meeting_at.date().isoformat(),
                "training_meetings": len(training),
                "policy_rate_upper": policy_rate,
                "zlb": policy_rate <= ZLB_UPPER_BOUND,
                "outcome": meeting.decision.value,
                "cut": probability,
                "hold": hold_probability,
                "hike": hike_probability,
                "climatology_cut": baseline,
                "climatology_hold": baseline_hold,
                "climatology_hike": baseline_hike,
                "intercept_only_cut": intercept_only,
            }
        )

    model_brier = brier_score(model_records)
    baseline_brier = brier_score(baseline_records)
    always_hold_brier = brier_score(always_hold_records)
    intercept_only_brier = brier_score(intercept_records)

    non_zlb_model = [record for record, zlb in zip(model_records, zlb_flags, strict=True) if not zlb]
    non_zlb_baseline = [
        record for record, zlb in zip(baseline_records, zlb_flags, strict=True) if not zlb
    ]
    non_zlb_hold = [
        record for record, zlb in zip(always_hold_records, zlb_flags, strict=True) if not zlb
    ]
    non_zlb_evaluated = len(non_zlb_model)
    non_zlb_model_brier = brier_score(non_zlb_model) if non_zlb_model else None
    non_zlb_climatology_brier = brier_score(non_zlb_baseline) if non_zlb_baseline else None
    non_zlb_always_hold_brier = brier_score(non_zlb_hold) if non_zlb_hold else None

    return WalkForwardReport(
        evaluated_meetings=len(model_records),
        non_zlb_evaluated_meetings=non_zlb_evaluated,
        actual_cuts=sum(record.outcome for record in model_records),
        model_brier=model_brier,
        sequential_climatology_brier=baseline_brier,
        always_hold_brier=always_hold_brier,
        intercept_only_brier=intercept_only_brier,
        brier_skill_vs_climatology=1.0 - model_brier / baseline_brier,
        brier_skill_vs_always_hold=_skill(model_brier, always_hold_brier),
        brier_skill_vs_intercept_only=1.0 - model_brier / intercept_only_brier,
        non_zlb_model_brier=non_zlb_model_brier,
        non_zlb_climatology_brier=non_zlb_climatology_brier,
        non_zlb_always_hold_brier=non_zlb_always_hold_brier,
        non_zlb_brier_skill_vs_climatology=(
            _skill(non_zlb_model_brier, non_zlb_climatology_brier)
            if non_zlb_model_brier is not None and non_zlb_climatology_brier is not None
            else None
        ),
        calibration_ece=expected_calibration_error(model_records, bins=5),
        minimum_sample_required=minimum_sample_required,
        climatology_gate_passed=non_zlb_evaluated >= minimum_sample_required
        and model_brier < baseline_brier,
        market_baseline_available=False,
        # D-007 requires positive out-of-sample skill against market prices.
        signal_eligible=False,
        three_way_brier=sum(three_way_errors) / len(model_records),
        three_way_climatology_brier=sum(three_way_baseline_errors) / len(model_records),
        hold_brier=sum(hold_errors) / len(model_records),
        hike_brier=sum(hike_errors) / len(model_records),
        actual_hikes=actual_hikes,
        predictions=predictions,
    )
