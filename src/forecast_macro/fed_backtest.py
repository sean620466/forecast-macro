from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time

from forecast_macro.datasets import HistoricalFomcRow
from forecast_macro.evaluation import ForecastRecord, brier_score, expected_calibration_error
from forecast_macro.fomc import RateDecision
from forecast_macro.models.fed import rate_decision_probabilities


@dataclass(frozen=True)
class FedBacktestPrediction:
    meeting_date: str
    probability_cut: float
    baseline_probability_cut: float
    actual_cut: int
    squared_error: float
    # D-016 three-way view; probability_cut equals probability_hold + probability_hike's complement.
    probability_hold: float = 0.0
    probability_hike: float = 0.0
    actual_decision: str = ""


@dataclass(frozen=True)
class FedBacktestReport:
    total_meetings: int
    evaluated_meetings: int
    non_zlb_evaluated_meetings: int
    warmup_meetings: int
    actual_cuts: int
    model_brier: float
    sequential_climatology_brier: float
    always_hold_brier: float
    constant_50_brier: float
    brier_skill_vs_climatology: float
    brier_skill_vs_always_hold: float | None
    calibration_ece: float
    minimum_sample_required: int
    passes_climatology_gate: bool
    market_baseline_available: bool
    signal_eligible: bool
    predictions: list[FedBacktestPrediction]
    # D-016: three-way Brier = sum over cut/hold/hike of squared error, averaged over meetings.
    three_way_brier: float = 0.0
    three_way_climatology_brier: float = 0.0
    hold_brier: float = 0.0
    hike_brier: float = 0.0
    actual_hikes: int = 0
    # D-017: meetings with a same-day 08:30 ET data release (None when snapshots lack the flag).
    same_day_release_meetings: int | None = None
    model_brier_excluding_same_day: float | None = None
    climatology_brier_excluding_same_day: float | None = None

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
    always_hold_records: list[ForecastRecord] = []
    same_day_flags: list[bool | None] = []
    prior_cuts = sum(row.decision is RateDecision.CUT for row in meetings[:warmup])
    prior_hikes = sum(row.decision is RateDecision.HIKE for row in meetings[:warmup])
    three_way_errors: list[float] = []
    three_way_baseline_errors: list[float] = []
    hold_errors: list[float] = []
    hike_errors: list[float] = []

    for index, meeting in enumerate(meetings[warmup:], start=warmup):
        snapshot = by_date[meeting.meeting_at.date().isoformat()]
        policy_rate = float(snapshot["policy_rate_upper"])
        if abs(policy_rate - meeting.upper_before) > 1e-9:
            raise ValueError(f"policy-rate snapshot mismatch for {meeting.meeting_at.date()}")
        # Task 46: the heuristic's hike/hold split is the climatology frequency of hikes among
        # prior non-cut meetings (Laplace-smoothed), not the mirrored cut score.
        prior_non_cuts = index - prior_cuts
        estimates = {
            item.outcome: item.probability
            for item in rate_decision_probabilities(
                inflation_yoy=float(snapshot["cpi_yoy_nsa"]),
                unemployment_rate=float(snapshot["unemployment_rate"]),
                unemployment_change_3m=float(snapshot["unemployment_change_3m"]),
                policy_rate=policy_rate,
                hike_given_no_cut=(prior_hikes + 1) / (prior_non_cuts + 2),
            )
        }
        probability = estimates["cut"]
        outcome = int(meeting.decision is RateDecision.CUT)
        same_day_flags.append(snapshot.get("same_day_release"))
        is_hike = int(meeting.decision is RateDecision.HIKE)
        is_hold = int(meeting.decision is RateDecision.HOLD)
        # Laplace smoothing prevents a zero baseline before the first historical cut.
        baseline_probability = (prior_cuts + 1) / (index + 2)
        baseline_hike = (prior_hikes + 1) / (index + 3)
        baseline_hold = max(0.0, 1.0 - baseline_probability - baseline_hike)
        three_way_errors.append(
            (probability - outcome) ** 2
            + (estimates["hold"] - is_hold) ** 2
            + (estimates["hike"] - is_hike) ** 2
        )
        three_way_baseline_errors.append(
            (baseline_probability - outcome) ** 2
            + (baseline_hold - is_hold) ** 2
            + (baseline_hike - is_hike) ** 2
        )
        hold_errors.append((estimates["hold"] - is_hold) ** 2)
        hike_errors.append((estimates["hike"] - is_hike) ** 2)
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
        always_hold_records.append(ForecastRecord(forecast_at, meeting.meeting_at, 0.0, outcome))
        predictions.append(
            FedBacktestPrediction(
                meeting_date=meeting.meeting_at.date().isoformat(),
                probability_cut=probability,
                baseline_probability_cut=baseline_probability,
                actual_cut=outcome,
                squared_error=(probability - outcome) ** 2,
                probability_hold=estimates["hold"],
                probability_hike=estimates["hike"],
                actual_decision=meeting.decision.value,
            )
        )
        prior_cuts += outcome
        prior_hikes += is_hike

    model_brier = brier_score(model_records)
    climate_brier = brier_score(climatology_records)
    always_hold_brier = brier_score(always_hold_records)
    evaluated = len(predictions)
    non_zlb_evaluated = sum(
        float(by_date[row.meeting_at.date().isoformat()]["policy_rate_upper"]) > 0.25
        for row in meetings[warmup:]
    )
    return FedBacktestReport(
        total_meetings=len(meetings),
        evaluated_meetings=evaluated,
        non_zlb_evaluated_meetings=non_zlb_evaluated,
        warmup_meetings=warmup,
        actual_cuts=sum(item.actual_cut for item in predictions),
        model_brier=model_brier,
        sequential_climatology_brier=climate_brier,
        always_hold_brier=always_hold_brier,
        constant_50_brier=brier_score(constant_records),
        brier_skill_vs_climatology=1.0 - model_brier / climate_brier,
        # Always-hold is perfect (Brier 0) when no cut occurred, so the ratio is undefined.
        brier_skill_vs_always_hold=(
            1.0 - model_brier / always_hold_brier if always_hold_brier > 0 else None
        ),
        calibration_ece=expected_calibration_error(model_records, bins=5),
        minimum_sample_required=minimum_sample_required,
        passes_climatology_gate=non_zlb_evaluated >= minimum_sample_required
        and model_brier < climate_brier,
        market_baseline_available=False,
        signal_eligible=False,
        predictions=predictions,
        three_way_brier=sum(three_way_errors) / evaluated,
        three_way_climatology_brier=sum(three_way_baseline_errors) / evaluated,
        hold_brier=sum(hold_errors) / evaluated,
        hike_brier=sum(hike_errors) / evaluated,
        actual_hikes=sum(item.actual_decision == "hike" for item in predictions),
        **_same_day_summary(same_day_flags, model_records, climatology_records),
    )


def _same_day_summary(
    flags: list[bool | None],
    model_records: list[ForecastRecord],
    climatology_records: list[ForecastRecord],
) -> dict[str, object]:
    if any(flag is None for flag in flags):
        return {}
    kept = [index for index, flag in enumerate(flags) if not flag]
    if not kept:
        return {"same_day_release_meetings": len(flags)}
    return {
        "same_day_release_meetings": sum(bool(flag) for flag in flags),
        "model_brier_excluding_same_day": brier_score([model_records[i] for i in kept]),
        "climatology_brier_excluding_same_day": brier_score([climatology_records[i] for i in kept]),
    }
