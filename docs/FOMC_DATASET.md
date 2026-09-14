# Verified FOMC Meeting Dataset

The initial dataset covers all 24 scheduled FOMC decisions from 2022 through 2024.

## Fields

- meeting date and 14:00 America/New_York decision time
- target-range upper bound immediately before and after the decision
- signed basis-point change
- cut, hold, or hike label
- primary Federal Reserve source URL

## Validation

The loader rejects rows when the stated basis-point change disagrees with the target bounds, the decision label disagrees with the calculated change, dates are unsorted, target ranges are discontinuous, or the source is not a Federal Reserve URL.

## Scope decision

2025 and 2026 will be added only after each meeting statement and target range are programmatically cross-checked. This avoids mixing future scheduled meetings with completed decisions.

## Realized decisions for scoring (task 48)

The history CSVs above are reviewed fixtures: their feature snapshots are checked in and
regression tests pin their length. They are extended by hand, together with a snapshot
rebuild. Scoring cannot wait for that, so the daily workflow keeps a second file with the
same schema, `data/generated/fomc_decisions.csv`, written by `scripts/record_fomc_decisions.py`:

1. Every scheduled decision in `data/release_schedule.csv` whose time has passed and that
   neither file carries is pending.
2. Its press release (`monetary<YYYYMMDD>a.htm`, the same D-002 source the history cites) is
   fetched and the decision sentence parsed ("the Committee decided to maintain/lower/raise
   the target range for the federal funds rate … X to Y percent"). Dissents ("preferred to")
   are ignored; the verb must agree with the change from the previous upper bound.
3. The row is validated with `load_fomc_history` (continuity, label, source URL) before the
   file is replaced. `scripts/score_fed_comparisons.py` merges the file into the history; a
   row that overlaps the history must match it exactly.

If the statement cannot be fetched within six hours of the decision the run fails and
`alerts.yml` opens a `workflow-failure` issue. Manual fallback: save the press release page
and run

```bash
python scripts/record_fomc_decisions.py --statement-file monetary20260916a.htm
```

then commit `data/generated/fomc_decisions.csv`. To check fetch and parsing from a GitHub
runner without waiting for a meeting, dispatch "Compare Fed model with market" with
`verify_statement_fetch=true`: it re-parses the last labelled meeting's statement and
compares it with the history row.

Extending the training history (`fomc_meetings_2015_2026.csv` and its snapshots) remains a
deliberate step; the live model's training sample does not grow from this file.
