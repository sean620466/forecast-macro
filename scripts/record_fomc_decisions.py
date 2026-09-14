"""Append realized FOMC decisions to the bot-owned label file (task 48, D-007 loop).

For every scheduled decision the release calendar says has been announced and that neither
the meeting history nor `data/generated/fomc_decisions.csv` carries, fetch the decision press
release, parse the target range and append a validated row. Exit 1 when a decision older
than the grace period still cannot be recorded, so the failure-alert workflow opens an issue.
Nothing here trains a model or changes `signal_eligible`.
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from forecast_macro.datasets import HistoricalFomcRow, load_fomc_history
from forecast_macro.fomc_decisions import (
    DEFAULT_REALIZED_PATH,
    StatementUnavailable,
    append_decision_row,
    fetch_statement,
    load_realized_decisions,
    merge_decisions,
    overdue,
    parse_statement,
    pending_meetings,
    press_release_url,
    realized_decision_row,
)
from forecast_macro.release_schedule import load_release_schedule


def verify_last(row: HistoricalFomcRow) -> int:
    """Fetch and parse the statement of an already-labelled meeting; it must reproduce the row."""
    url = press_release_url(row.meeting_at.date())
    try:
        parsed = parse_statement(fetch_statement(url))
    except (StatementUnavailable, ValueError) as exc:
        print(f"ERROR: could not verify {url}: {exc}", file=sys.stderr)
        return 1
    if parsed.upper != row.upper_after or parsed.decision is not row.decision:
        print(
            f"ERROR: {url} parsed as {parsed.decision.value} to {parsed.upper} but the history says "
            f"{row.decision.value} to {row.upper_after}",
            file=sys.stderr,
        )
        return 1
    print(f"verified {row.meeting_at.date()}: {parsed.decision.value} {parsed.lower}–{parsed.upper} from {url}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--meetings", type=Path, default=Path("data/fomc_meetings_2019_2026.csv"))
    parser.add_argument("--realized", type=Path, default=DEFAULT_REALIZED_PATH)
    parser.add_argument("--schedule", type=Path, default=Path("data/release_schedule.csv"))
    parser.add_argument("--as-of", type=datetime.fromisoformat, default=None, help="timezone-aware ISO timestamp")
    parser.add_argument(
        "--grace-hours",
        type=float,
        default=6.0,
        help="a statement missing this long after the decision time fails the run",
    )
    parser.add_argument(
        "--statement-file",
        type=Path,
        default=None,
        help="parse this saved press release instead of fetching (offline fallback for the next pending meeting)",
    )
    parser.add_argument(
        "--verify-last",
        action="store_true",
        help="fetch the last labelled meeting's statement and check the parse against its row (network self-test)",
    )
    args = parser.parse_args()

    as_of = args.as_of or datetime.now(UTC)
    if as_of.tzinfo is None:
        raise SystemExit("--as-of must be timezone-aware")
    known = merge_decisions(load_fomc_history(args.meetings), load_realized_decisions(args.realized))
    if args.verify_last:
        return verify_last(known[-1])
    pending = pending_meetings(load_release_schedule(args.schedule), known=known, as_of=as_of)
    if not pending:
        print(f"no unlabelled FOMC decision as of {as_of.isoformat()} (last label {known[-1].meeting_at.date()})")
        return 0

    for meeting in pending:
        url = press_release_url(meeting.release_at.date())
        try:
            if args.statement_file is not None:
                statement = args.statement_file.read_text(encoding="utf-8")
                args.statement_file = None  # one file labels one meeting
            else:
                statement = fetch_statement(url)
        except StatementUnavailable as exc:
            if overdue(meeting, as_of=as_of, grace=timedelta(hours=args.grace_hours)):
                print(
                    f"ERROR: {meeting.release_at.date()} decided at {meeting.release_at.isoformat()} but "
                    f"{url} is unavailable ({exc}); save the statement and rerun with --statement-file, "
                    "see docs/FOMC_DATASET.md",
                    file=sys.stderr,
                )
                return 1
            print(f"{meeting.release_at.date()}: statement not available yet ({exc}); retrying next run")
            return 0
        row = realized_decision_row(meeting, upper_before=known[-1].upper_after, statement=statement, source=url)
        rows = append_decision_row(args.realized, row)
        known = merge_decisions(known, rows)
        print(
            f"recorded {row['meeting_date']}: {row['decision']} {row['upper_before']} -> {row['upper_after']} "
            f"({row['change_bps']} bps) from {url}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
