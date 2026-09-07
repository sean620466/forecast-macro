from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time

from forecast_macro.datasets import HistoricalFomcRow
from forecast_macro.evaluation import ForecastRecord, brier_score, expected_calibration_error
from forecast_macro.fomc import RateDecision
from forecast_macro.models.fed import rate_cut_probability


@dataclass(frozen=True)
class FedBacktestPrediction:
    meeting_date: str
    probability_cut: float
    baseline_probability_cut: float
    actual_cut: int
    squared_error: float


@dataclass(frozen=True)
class FedBacktestReport:
    total_meetings: int
    evaluated_meetings: int
    warmup_meetings: int
    actual_cuts: int
    model_brier: float
    sequential_climatology_brier: float
    constant_50_brier: float
    brier_skill_vs_climatology: float
    calibration_ece: float
    minimum_sample_required: int
    signal_eligible: bool
    predictions: list[FedBacktestPrediction]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def run_fed_baseline_backtest(
    meetings: list[HistoricalFomcRow],
    snapshots: list[dict[str, object]],
    *,
    warmup: int = 8,
    minimum_sample_required: int = 30,
) -> FedBacktestReport:
    if warmup < 1 or warmup >= len(meetings):
        raise ValueError("warmup must leave at least one evaluation meeting")
    by_date = {str(row["meeting_date"]): row for row in snapshots}
    if len(by_date) != len(snapshots):
        raise ValueError("snapshot meeting dates must be unique")
    missing = [row.meeting_at.date().isoformat() for row in meetings if row.meeting_at.date().isoformat() not in by_date]
    if missing:
        raise ValueError(f"missing snapshots: {', '.join(missing)}")

    predictions: list[FedBacktestPrediction] = []
    model_records: list[ForecastRecord] = []
    climatology_records: list[ForecastRecord] = []
    constant_records: list[ForecastRecord] = []
    prior_cuts = sum(row.decision is RateDecision.CUT for row in meetings[:warmup])

    for index, meeting in enumerate(meetings[warmup:], start=warmup):
        snapshot = by_date[meeting.meeting_at.date().isoformat()]
        policy_rate = float(snapshot["policy_rate_upper"])
        if abs(policy_rate - meeting.upper_before) > 1e-9:
            raise ValueError(f"policy-rate snapshot mismatch for {meeting.meeting_at.date()}")
        estimates = rate_cut_probability(
            inflation_yoy=float(snapshot["cpi_yoy_nsa"]),
            unemployment_rate=float(snapshot["unemployment_rate"]),
            unemployment_change_3m=float(snapshot["unemployment_change_3m"]),
            policy_rate=policy_rate,
        )
        probability = next(item.probability for item in estimates if item.outcome == "cut")
        outcome = int(meeting.decision is RateDecision.CUT)
        # Laplace smoothing prevents a zero baseline before the first historical cut.
        baseline_probability = (prior_cuts + 1) / (index + 2)
        forecast_at = datetime.combine(
            datetime.fromisoformat(str(snapshot["vintage_date"])).date(),
            time(23, 59),
            tzinfo=UTC,
        )
        model_records.append(ForecastRecord(forecast_at, meeting.meeting_at, probability, outcome))
        climatology_records.append(
            ForecastRecord(forecast_at, meeting.meeting_at, baseline_probability, outcome)
        )
        constant_records.append(ForecastRecord(forecast_at, meeting.meeting_at, 0.5, outcome))
        predictions.append(
            FedBacktestPrediction(
                meeting_date=meeting.meeting_at.date().isoformat(),
                probability_cut=probability,
                baseline_probability_cut=baseline_probability,
                actual_cut=outcome,
                squared_error=(probability - outcome) ** 2,
            )
        )
        prior_cuts += outcome

    model_brier = brier_score(model_records)
    climate_brier = brier_score(climatology_records)
    evaluated = len(predictions)
    return FedBacktestReport(
        total_meetings=len(meetings),
        evaluated_meetings=evaluated,
        warmup_meetings=warmup,
        actual_cuts=sum(item.actual_cut for item in predictions),
        model_brier=model_brier,
        sequential_climatology_brier=climate_brier,
        constant_50_brier=brier_score(constant_records),
        brier_skill_vs_climatology=1.0 - model_brier / climate_brier,
        calibration_ece=expected_calibration_error(model_records, bins=5),
        minimum_sample_required=minimum_sample_required,
        signal_eligible=evaluated >= minimum_sample_required and model_brier < climate_brier,
        predictions=predictions,
    )
