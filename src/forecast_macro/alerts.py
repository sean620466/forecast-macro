"""Alerts for the D-007 loop (task 38).

Two things are worth interrupting a person for:

1. a scheduled workflow failed (handled in `.github/workflows/alerts.yml` from the run
   conclusion; nothing here), and
2. an outcome was realized and scored, so the model-vs-market record grew by one.

This module turns the second into a GitHub issue body. It compares the scoring files the
daily workflow just produced with the versions committed before the run and describes the
newly scored records. Pure functions only; the workflow feeds them files and posts the
result with the GitHub CLI. Nothing here changes `signal_eligible`, which stays false in
code regardless of what the scores say (D-012).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TopicSpec:
    topic: str
    label: str
    record_key: str  # field identifying one scored outcome
    count_field: str


TOPICS: dict[str, TopicSpec] = {
    "fed": TopicSpec("fed", "FOMC 금리 결정", "meeting_date", "scored_meetings"),
    "unemployment": TopicSpec("unemployment", "실업률 발표", "reference_period", "scored_releases"),
    "core_cpi": TopicSpec("core_cpi", "Core CPI YoY 발표", "reference_period", "scored_releases"),
}


@dataclass(frozen=True)
class ScoringAlert:
    topic: str
    title: str
    body: str
    labels: tuple[str, ...] = ("scoring",)


def new_scored_records(
    previous: Mapping[str, Any] | None, current: Mapping[str, Any], record_key: str
) -> list[Mapping[str, Any]]:
    """Records present in `current` whose key was not scored in `previous`."""
    seen = {str(row[record_key]) for row in (previous or {}).get("records", [])}
    return [row for row in current.get("records", []) if str(row[record_key]) not in seen]


def _pct(value: Any) -> str:
    return "–" if value is None else f"{float(value) * 100:.1f}%"


def _num(value: Any, digits: int = 3) -> str:
    return "–" if value is None else f"{float(value):.{digits}f}"


def _fed_record_lines(row: Mapping[str, Any]) -> list[str]:
    outcome = row.get("outcome") or ("cut" if row.get("outcome_cut") else "no cut")
    lines = [
        f"- 회의 {row['meeting_date']}: 실제 **{outcome}** (상단 금리 {row.get('policy_rate_upper')}%)",
        f"  - 마지막 기록 시각: {row.get('as_of')}",
        (
            f"  - 인하 확률 — 로지스틱 {_pct(row.get('logistic_cut'))}, 휴리스틱 {_pct(row.get('heuristic_cut'))}, "
            f"시장 {_pct(row.get('market_cut'))} [{_pct(row.get('market_lower'))}, {_pct(row.get('market_upper'))}]"
        ),
    ]
    if row.get("logistic_three_way_error") is not None:
        lines.append(
            f"  - 3원 제곱오차 — 로지스틱 {_num(row.get('logistic_three_way_error'))}, "
            f"시장 {_num(row.get('market_three_way_error'))} (낮을수록 좋음)"
        )
    flags = [name for name in ("same_day_release", "low_liquidity") if row.get(name)]
    if flags:
        lines.append(f"  - 플래그: {', '.join(flags)} (D-017/D-018, 헤드라인 집계에서 제외)")
    return lines


def _bucket_record_lines(row: Mapping[str, Any]) -> list[str]:
    return [
        (
            f"- 기준월 {row['reference_period']} (발표 {row.get('release_at')}): 실제 **{row.get('realized_rate')}** "
            f"→ 구간 `{row.get('realized_bucket')}`"
        ),
        (
            f"  - 실제 구간에 준 확률 — 모델 {_pct(row.get('model_probability_of_realized'))}, "
            f"시장 {_pct(row.get('market_probability_of_realized'))}"
        ),
        f"  - 다중구간 Brier — 모델 {_num(row.get('model_brier'))}, 시장 {_num(row.get('market_brier'))} (낮을수록 좋음)",
    ]


def _aggregate_lines(spec: TopicSpec, scorecard: Mapping[str, Any]) -> list[str]:
    count = scorecard.get(spec.count_field)
    minimum = scorecard.get("minimum_sample_required")
    lines = [f"- 누적 채점: **{count}건** / 표본 게이트 {minimum}건 (D-013)"]
    if spec.topic == "fed":
        lines.append(
            f"- 로지스틱 Brier {_num(scorecard.get('logistic_brier'))} vs 시장 {_num(scorecard.get('market_brier'))}; "
            f"시장 대비 skill {_num(scorecard.get('logistic_skill_vs_market'))}"
        )
        if scorecard.get("clean_meetings"):
            lines.append(
                f"- 클린 부분표본 {scorecard.get('clean_meetings')}건: 로지스틱 {_num(scorecard.get('clean_logistic_brier'))} "
                f"vs 시장 {_num(scorecard.get('clean_market_brier'))}"
            )
    else:
        lines.append(
            f"- 모델 Brier {_num(scorecard.get('model_brier'))} vs 시장 {_num(scorecard.get('market_brier'))}; "
            f"시장 대비 skill {_num(scorecard.get('model_skill_vs_market'))}"
        )
    lines.append(
        f"- signal_eligible: `{scorecard.get('signal_eligible', False)}` — {scorecard.get('signal_eligible_reason', '')}"
    )
    return lines


def scoring_alert(
    spec: TopicSpec,
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
    *,
    run_url: str = "",
) -> ScoringAlert | None:
    rows = new_scored_records(previous, current, spec.record_key)
    if not rows:
        return None
    keys = ", ".join(str(row[spec.record_key]) for row in rows)
    title = f"[채점] {spec.label} {keys}: 모델 vs 시장 결과"
    body_lines = [
        f"## {spec.label} — 새로 채점된 {len(rows)}건",
        "",
        "결과가 확정되어 마지막 기록이 채점되었습니다. 이 이슈는 알림일 뿐이며 어떤 신호도 만들지 않습니다 (D-012).",
        "",
    ]
    for row in rows:
        body_lines.extend(_fed_record_lines(row) if spec.topic == "fed" else _bucket_record_lines(row))
    body_lines += ["", "### 누적 상태", *_aggregate_lines(spec, current)]
    if run_url:
        body_lines += ["", f"워크플로 실행: {run_url}"]
    body_lines += ["", "자세한 수치: `STATUS.md`, `docs/dashboard/index.html`."]
    return ScoringAlert(topic=spec.topic, title=title, body="\n".join(body_lines) + "\n")


def build_scoring_alerts(
    previous_by_topic: Mapping[str, Mapping[str, Any] | None],
    current_by_topic: Mapping[str, Mapping[str, Any]],
    *,
    run_url: str = "",
) -> list[ScoringAlert]:
    alerts: list[ScoringAlert] = []
    for topic, current in current_by_topic.items():
        spec = TOPICS[topic]
        alert = scoring_alert(spec, previous_by_topic.get(topic), current, run_url=run_url)
        if alert is not None:
            alerts.append(alert)
    return alerts


def alert_files(alerts: Sequence[ScoringAlert]) -> dict[str, str]:
    """File name → contents; the first line is the issue title, the rest the body."""
    return {f"{alert.topic}.md": f"{alert.title}\n{alert.body}" for alert in alerts}
