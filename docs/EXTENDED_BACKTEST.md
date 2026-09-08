# Extended Fed baseline backtest (2019–2024)

## Result

The ZLB-aware evaluation improves materially, but signals remain disabled. Only non-ZLB
meetings count toward the strengthened research sample floor, and no market-price baseline
is available yet.

| Scope | OOS | Non-ZLB OOS | Cuts | Model Brier | Climatology | Always hold | BSS vs climatology | BSS vs always hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| All decisions | 41 | 25 | 5 | 0.077271 | 0.127604 | 0.121951 | +0.394449 | +0.366381 |
| Scheduled only | 39 | 23 | 3 | 0.049031 | 0.095612 | 0.076923 | +0.487186 | +0.362597 |
| Window (contract-style) | 38 | 23 | 3 | 0.050321 | 0.097596 | 0.078947 | +0.484399 | +0.362605 |

Scopes differ only in how the March 2020 emergency cuts are treated:

- **All decisions** scores the two emergency decisions as their own events. Knowing that an
  emergency meeting happened is itself hindsight, so this scope is kept for completeness, not
  as the reference.
- **Scheduled only** drops the emergency rows. That leaves a rate gap (1.75% after January 29
  to 0.25% before April 29), which `run_fed_backtest.py` now refuses unless
  `--allow-rate-gaps` is passed. The checked-in file was produced with that flag.
- **Window** labels each scheduled meeting by the change since the previous scheduled
  decision, the way rate contracts settle. The April 29, 2020 window (-150bp) was already
  decided by March 15, before any prior-day forecast could be made, so it is reported in
  `dropped_predetermined_windows` and not scored. With one full cycle in the sample, window
  scope is therefore scheduled scope minus one row; the distinction will matter in any
  future window that contains an intermeeting move.

All runs use an eight-event warmup and point-in-time ALFRED snapshots from the prior
calendar day. Every decision row cites its own Federal Reserve press release
(`monetaryYYYYMMDDa.htm`), and the loader rejects generic calendar URLs.

## Interpretation

The original negative result was dominated by a structural error: it allowed very high cut
probabilities while the target upper bound was already 0.25%. D-011 now assigns a fixed
0.005 cut probability at the ZLB and clips all other probabilities away from exact zero and
one. This constraint was registered as prior institutional knowledge, not tuned as a fitted
coefficient.

The improvement is diagnostic rather than proof of general forecasting skill. There are
only 25 all-decision and 23 scheduled non-ZLB observations, below D-013's 30-observation
research floor, and only three evaluated scheduled cuts. D-007 also requires comparison
against actual market prices. `signal_eligible` therefore remains false.

## Reproduce

```bash
python scripts/run_fed_backtest.py \
  --meetings data/fomc_meetings_2019_2024.csv \
  --snapshots data/generated/fomc_feature_snapshots_2019_2024.json \
  --event-scope all \
  --output data/generated/fed_baseline_backtest_all_2019_2024.json

python scripts/run_fed_backtest.py \
  --meetings data/fomc_meetings_2019_2024.csv \
  --snapshots data/generated/fomc_feature_snapshots_2019_2024.json \
  --event-scope scheduled --allow-rate-gaps \
  --output data/generated/fed_baseline_backtest_scheduled_2019_2024.json

python scripts/run_fed_backtest.py \
  --meetings data/fomc_meetings_2019_2024.csv \
  --snapshots data/generated/fomc_feature_snapshots_2019_2024.json \
  --event-scope window \
  --output data/generated/fed_baseline_backtest_window_2019_2024.json
```

`tests/test_review_4_followups.py` recomputes the all and window files and compares them to
the checked-in JSON.

The successful snapshot build is GitHub Actions run `34155616512`; its artifact contains
49 complete snapshots with no null fields.

## 2019–2026 rerun (task 15)

| Scope | OOS | Non-ZLB OOS | Cuts | Model Brier | Climatology | Always hold | BSS vs climatology | BSS vs always hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| All decisions | 54 | 38 | 8 | 0.102073 | 0.140890 | 0.148148 | +0.275529 | +0.310724 |
| Window | 51 | 36 | 6 | 0.083525 | 0.120273 | 0.117647 | +0.305824 | +0.290326 |

Files: `fed_baseline_backtest_{all,scheduled,window}_2019_2026.json`. October 2025 CPI and
unemployment were never published (2025 shutdown); the affected snapshots record that month in
`data_gaps` and the 12-month and 3-month changes use their endpoints. The 2019–2024 files are
untouched and their regression tests still pass.
