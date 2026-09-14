"""Task 48: the first D-007 scoring after a decision must not wait for a hand-edited CSV.

The Fed scorer labels a meeting only from `data/fomc_meetings_2019_2026.csv`, which is
transcribed by hand and pinned by regression fixtures. These tests cover the bot-owned label
path: statement parsing, the pending-meeting rule, validated appends, the merge into the
history, and the end-to-end run of the recording and scoring scripts on the committed
comparison records for the 2026-09-16 meeting.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from forecast_macro.alerts import build_scoring_alerts
from forecast_macro.comparison_scoring import load_comparison_records, score_comparisons
from forecast_macro.datasets import load_fomc_history, scheduled_meetings
from forecast_macro.fomc import RateDecision
from forecast_macro.fomc_decisions import (
    append_decision_row,
    load_realized_decisions,
    merge_decisions,
    parse_statement,
    pending_meetings,
    press_release_url,
    realized_decision_row,
)
from forecast_macro.release_schedule import load_release_schedule

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data" / "fomc_meetings_2019_2026.csv"
SCHEDULE = load_release_schedule(ROOT / "data" / "release_schedule.csv")
MEETING_0916 = next(r for r in SCHEDULE if r.series == "fomc" and r.release_at.date().isoformat() == "2026-09-16")


def _page(body: str) -> str:
    return (
        "<html><head><title>Federal Reserve Board - Federal Reserve issues FOMC statement</title></head>"
        f"<body><div class='col-xs-12'><p>{body}</p><p>Voting for the monetary policy action were "
        "Jerome H. Powell, Chair; John C. Williams, Vice Chair.</p></div></body></html>"
    )


HOLD = _page(
    "In support of its goals, the Committee decided to maintain the target range for the federal "
    "funds rate at 3&#8209;1/2 to 3-3/4 percent. In considering the extent and timing of additional "
    "adjustments, the Committee will carefully assess incoming data."
)
CUT = _page(
    "In support of its goals and in light of the shift in the balance of risks, the Committee decided "
    "to lower the target range for the federal funds rate by 1/4 percentage point to 3-1/2 to 3-3/4 percent."
)
HIKE = _page(
    "The Committee decided to raise the target range for the federal funds rate to 1-1/2 to 1-3/4 "
    "percent and anticipates that ongoing increases in the target range will be appropriate."
)
ZLB = _page(
    "The Committee decided to lower the target range for the federal funds rate to 0 to 1/4 percent. "
    "The Committee expects to maintain this target range until it is confident that the economy has weathered recent events."
)
REAFFIRMED_2015 = _page(
    "the Committee today reaffirmed its view that the current 0 to 1/4 percent target range for the "
    "federal funds rate remains appropriate."
)
CUT_WITH_DISSENT = _page(
    "the Committee decided to lower the target range for the federal funds rate by 1/4 percentage point "
    "to 3-1/2 to 3-3/4 percent. Voting against this action was Beth M. Hammack, who preferred to maintain "
    "the target range for the federal funds rate at 3-3/4 to 4 percent."
)


@pytest.mark.parametrize(
    "document, lower, upper, decision",
    [
        (HOLD, 3.5, 3.75, RateDecision.HOLD),
        (CUT, 3.5, 3.75, RateDecision.CUT),
        (HIKE, 1.5, 1.75, RateDecision.HIKE),
        (ZLB, 0.0, 0.25, RateDecision.CUT),
        (REAFFIRMED_2015, 0.0, 0.25, RateDecision.HOLD),
        (CUT_WITH_DISSENT, 3.5, 3.75, RateDecision.CUT),
    ],
)
def test_statement_parser_reads_the_decision_sentence(document, lower, upper, decision) -> None:
    parsed = parse_statement(document)
    assert (parsed.lower, parsed.upper, parsed.decision) == (lower, upper, decision)


def test_statement_parser_refuses_missing_or_conflicting_sentences() -> None:
    with pytest.raises(ValueError, match="no FOMC decision sentence"):
        parse_statement(_page("The Committee will continue to monitor the implications of incoming information."))
    conflicting = _page(
        "the Committee decided to maintain the target range for the federal funds rate at 3-1/2 to 3-3/4 percent. "
        "the Committee decided to maintain the target range for the federal funds rate at 3-3/4 to 4 percent."
    )
    with pytest.raises(ValueError, match="disagree"):
        parse_statement(conflicting)
    with pytest.raises(ValueError, match="quarter point"):
        parse_statement(_page("the Committee decided to maintain the target range for the federal funds rate at 3 to 3-3/4 percent."))


def test_realized_row_cross_checks_the_verb_against_the_prior_rate() -> None:
    row = realized_decision_row(MEETING_0916, upper_before=3.75, statement=HOLD)
    assert row == {
        "meeting_date": "2026-09-16",
        "decision_time_local": "14:00",
        "timezone": "America/New_York",
        "upper_before": "3.75",
        "upper_after": "3.75",
        "change_bps": "0",
        "decision": "hold",
        "event_type": "scheduled",
        "source": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm",
    }
    cut = realized_decision_row(MEETING_0916, upper_before=4.0, statement=CUT)
    assert (cut["decision"], cut["change_bps"]) == ("cut", "-25")
    # The statement says "lower" but the history's last upper bound already equals the new one.
    with pytest.raises(ValueError, match="statement says cut"):
        realized_decision_row(MEETING_0916, upper_before=3.75, statement=CUT)
    assert press_release_url(MEETING_0916.release_at.date()).endswith("monetary20260916a.htm")


def test_pending_meetings_follow_the_calendar_and_the_labels() -> None:
    history = load_fomc_history(HISTORY)
    before = datetime(2026, 9, 16, 17, 59, tzinfo=UTC)  # 13:59 ET, one minute before the decision
    assert pending_meetings(SCHEDULE, known=history, as_of=before) == []
    after = datetime(2026, 9, 17, 13, 40, tzinfo=UTC)  # the next weekday run
    assert [m.release_at.date().isoformat() for m in pending_meetings(SCHEDULE, known=history, as_of=after)] == [
        "2026-09-16"
    ]
    later = datetime(2026, 10, 29, 13, 40, tzinfo=UTC)
    assert [m.release_at.date().isoformat() for m in pending_meetings(SCHEDULE, known=history, as_of=later)] == [
        "2026-09-16",
        "2026-10-28",
    ]
    with pytest.raises(ValueError, match="timezone-aware"):
        pending_meetings(SCHEDULE, known=history, as_of=datetime(2026, 9, 17))  # noqa: DTZ001 — naive on purpose


def test_append_validates_and_merge_extends_the_history(tmp_path: Path) -> None:
    history = load_fomc_history(HISTORY)
    realized = tmp_path / "fomc_decisions.csv"
    assert load_realized_decisions(realized) == []
    realized.write_text("meeting_date,decision_time_local,timezone,upper_before,upper_after,change_bps,decision,event_type,source\n")
    assert load_realized_decisions(realized) == []

    rows = append_decision_row(realized, realized_decision_row(MEETING_0916, upper_before=3.75, statement=HOLD))
    assert [r.meeting_at.date().isoformat() for r in rows] == ["2026-09-16"]
    merged = merge_decisions(history, load_realized_decisions(realized))
    assert len(merged) == len(history) + 1 and merged[-1].decision is RateDecision.HOLD
    assert merged[: len(history)] == history
    # Re-merging rows the history already carries is a no-op when they agree.
    assert merge_decisions(merged, load_realized_decisions(realized)) == merged

    # A discontinuous row is rejected and the file is left as it was.
    bad = realized_decision_row(MEETING_0916, upper_before=4.0, statement=CUT)
    bad["meeting_date"] = "2026-10-28"
    bad["source"] = press_release_url(date(2026, 10, 28))
    with pytest.raises(ValueError, match="discontinuity"):
        append_decision_row(realized, bad)
    assert len(load_realized_decisions(realized)) == 1
    assert not (tmp_path / "fomc_decisions.csv.tmp").exists()

    # A realized row that contradicts the reviewed history is rejected too.
    wrong = load_realized_decisions(realized)[0]
    contradiction = wrong.__class__(**{**wrong.__dict__, "meeting_at": history[-1].meeting_at})
    with pytest.raises(ValueError, match="disagrees"):
        merge_decisions(history, [contradiction])


def test_first_live_meeting_scores_from_the_committed_records(tmp_path: Path) -> None:
    """The committed 2026-09-16 comparison records score once the realized row exists."""
    history = load_fomc_history(HISTORY)
    realized = tmp_path / "fomc_decisions.csv"
    append_decision_row(realized, realized_decision_row(MEETING_0916, upper_before=3.75, statement=HOLD))
    meetings = scheduled_meetings(merge_decisions(history, load_realized_decisions(realized)))
    records = load_comparison_records(ROOT / "data" / "generated" / "fed_market_comparisons")
    assert any(r["meeting_date"] == "2026-09-16" and r["market"] for r in records)

    card = score_comparisons(records, meetings=meetings)
    assert card.scored_meetings == 1 and card.non_zlb_meetings == 1
    scored = card.records[0]
    assert scored.meeting_date == "2026-09-16" and scored.outcome == "hold" and scored.outcome_cut == 0
    assert datetime.fromisoformat(scored.as_of) < MEETING_0916.release_at
    assert card.three_way_meetings == 1 and card.market_three_way_brier is not None
    assert card.signal_eligible is False and "D-013" in card.signal_eligible_reason
    # Without the realized row the same records score nothing: this is the gap task 48 closes.
    assert score_comparisons(records, meetings=scheduled_meetings(history)).scored_meetings == 0

    previous = json.loads((ROOT / "data" / "generated" / "fed_market_scoring.json").read_text())
    alerts = build_scoring_alerts({"fed": previous}, {"fed": card.to_dict()})
    assert len(alerts) == 1 and "2026-09-16" in alerts[0].title and "**hold**" in alerts[0].body


def test_scripts_record_then_score_end_to_end(tmp_path: Path) -> None:
    statement = tmp_path / "monetary20260916a.htm"
    statement.write_text(HOLD, encoding="utf-8")
    realized = tmp_path / "fomc_decisions.csv"
    env = {"PYTHONPATH": str(ROOT / "src")}
    record = [sys.executable, str(ROOT / "scripts" / "record_fomc_decisions.py"), "--realized", str(realized),
              "--as-of", "2026-09-17T13:40:00+00:00"]
    first = subprocess.run([*record, "--statement-file", str(statement)], cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stderr
    assert "recorded 2026-09-16: hold 3.75 -> 3.75 (0 bps)" in first.stdout
    with realized.open(newline="") as handle:
        assert [r["meeting_date"] for r in csv.DictReader(handle)] == ["2026-09-16"]

    # Idempotent: the next run finds nothing to label and does not touch the network.
    second = subprocess.run(record, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    assert second.returncode == 0 and "no unlabelled FOMC decision" in second.stdout
    assert "last label 2026-09-16" in second.stdout

    output = tmp_path / "scoring.json"
    score = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "score_fed_comparisons.py"), "--realized", str(realized), "--output", str(output)],
        cwd=ROOT, env=env, capture_output=True, text=True, check=False,
    )
    assert score.returncode == 0, score.stderr
    card = json.loads(output.read_text())
    assert card["scored_meetings"] == 1 and card["records"][0]["meeting_date"] == "2026-09-16"


def test_missing_statement_is_retried_within_grace_and_fails_after(tmp_path: Path) -> None:
    realized = tmp_path / "fomc_decisions.csv"
    env = {"PYTHONPATH": str(ROOT / "src"), "HTTPS_PROXY": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9"}
    base = [sys.executable, str(ROOT / "scripts" / "record_fomc_decisions.py"), "--realized", str(realized)]
    soon = subprocess.run([*base, "--as-of", "2026-09-16T19:00:00+00:00"], cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    assert soon.returncode == 0 and "retrying next run" in soon.stdout
    late = subprocess.run([*base, "--as-of", "2026-09-17T13:40:00+00:00"], cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    assert late.returncode == 1 and "--statement-file" in late.stderr
    assert not realized.exists()


def test_workflow_records_decisions_before_scoring_and_persists_the_file() -> None:
    text = (ROOT / ".github" / "workflows" / "compare-fed-market.yml").read_text()
    record = text.index("python scripts/record_fomc_decisions.py")
    score = text.index("python scripts/score_fed_comparisons.py")
    persist = text.index("data/generated/fomc_decisions.csv")
    assert record < score < persist
    assert "continue-on-error: true" in text and "steps.decisions.outcome == 'failure'" in text
    assert (ROOT / "data" / "generated" / "fomc_decisions.csv").read_text().splitlines() == [
        "meeting_date,decision_time_local,timezone,upper_before,upper_after,change_bps,decision,event_type,source"
    ]
