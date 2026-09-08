from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time

from forecast_macro.datasets import HistoricalFomcRow
from forecast_macro.evaluation import ForecastRecord, brier_score, expected_calibration_error
from forecast_macro.fomc import RateDecision
from forecast_macro.models.fed import ZLB_UPPER_BOUND, apply_cut_feasibility
from forecast_macro.models.logistic import fit_logistic


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

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _features(snapshot: dict[str, object]) -> tuple[float, ...]:
    return (
        float(snapshot["cpi_yoy_nsa"]),
        float(snapshot["unemployment_rate"]),
        float(snapshot["unemployment_change_3m"]),
        float(snapshot["policy_rate_upper"]),
    )


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
    for index in range(warmup, len(meetings)):
        training = meetings[:index]
        training_snapshots = [by_date[row.meeting_at.date().isoformat()] for row in training]
        model = fit_logistic(
            [_features(snapshot) for snapshot in training_snapshots],
            [int(row.decision is RateDecision.CUT) for row in training],
        )
        meeting = meetings[index]
        snapshot = by_date[meeting.meeting_at.date().isoformat()]
        policy_rate = float(snapshot["policy_rate_upper"])
        probability = apply_cut_feasibility(
            model.predict(_features(snapshot)), policy_rate=policy_rate
        )
        intercept_only = apply_cut_feasibility(_sigmoid(model.intercept), policy_rate=policy_rate)
        outcome = int(meeting.decision is RateDecision.CUT)
        prior_cuts = sum(row.decision is RateDecision.CUT for row in training)
        baseline = (prior_cuts + 1) / (len(training) + 2)
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
    )
