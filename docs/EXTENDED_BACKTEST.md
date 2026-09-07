# Extended Fed baseline backtest (2019–2024)

## Result

The evaluation now clears the D-007 sample-size floor, but the baseline model does not
clear the skill requirement. Signals therefore remain disabled.

| Scope | Events | OOS predictions | Cuts | Model Brier | Sequential climatology Brier | BSS | Eligible |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| All decisions | 49 | 41 | 5 | 0.141745 | 0.127604 | -0.110820 | No |
| Scheduled only | 47 | 39 | 3 | 0.116812 | 0.095612 | -0.221731 | No |

The all-decisions scope explicitly includes the emergency cuts of March 3 and March 15,
2020. The scheduled-only scope excludes them rather than silently treating them as ordinary
meetings. Both runs use an eight-event warmup and point-in-time ALFRED snapshots from the
prior calendar day.

## Interpretation

The earlier 2022–2024 result was positive but had only 16 out-of-sample predictions. Once
the history is extended beyond 30 observations, the simple fixed-form Fed model performs
worse than a Laplace-smoothed sequential cut-rate baseline. D-007 correctly blocks signal
publication. The next modeling step must improve genuine out-of-sample skill rather than
relax the gate.

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
