# Extended Fed baseline backtest (2019–2024)

## Result

The ZLB-aware evaluation improves materially, but signals remain disabled. Only non-ZLB
meetings count toward the strengthened research sample floor, and no market-price baseline
is available yet.

| Scope | OOS | Non-ZLB OOS | Model Brier | Climatology | Always hold | BSS vs climatology |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All decisions | 41 | 25 | 0.077271 | 0.127604 | 0.121951 | +0.394449 |
| Scheduled only | 39 | 23 | 0.049031 | 0.095612 | 0.076923 | +0.487186 |

The all-decisions scope explicitly includes the emergency cuts of March 3 and March 15,
2020. The scheduled-only scope excludes them rather than silently treating them as ordinary
meetings. Both runs use an eight-event warmup and point-in-time ALFRED snapshots from the
prior calendar day.

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
  --event-scope scheduled \
  --output data/generated/fed_baseline_backtest_scheduled_2019_2024.json
```

The successful snapshot build is GitHub Actions run `34155616512`; its artifact contains
49 complete snapshots with no null fields.
