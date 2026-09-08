# Walk-forward Fed model candidate

The fixed-form heuristic failed the extended 2019–2024 test. This candidate replaces it
with a deterministic ridge-logistic model using the same four point-in-time features:
CPI YoY, unemployment, three-month unemployment change, and the target-range upper bound.

For every prediction, scaling and coefficients are fitted again using only earlier FOMC
decisions. No future observation or outcome enters training. The information cutoff is the
end of the prior-day ALFRED vintage, the same rule `fed_backtest` uses.

## Scheduled-meeting result

| Metric | All 39 | Non-ZLB 23 |
| --- | ---: | ---: |
| Actual cuts | 3 | 3 |
| Model Brier | 0.067791 | 0.114932 |
| Sequential climatology Brier | 0.095612 | 0.122169 |
| Always-hold Brier (p = 0) | 0.076923 | 0.130435 |
| Intercept-only + ZLB mask Brier | 0.072898 | — |
| BSS vs climatology | +0.290978 | +0.059238 |
| BSS vs always-hold | +0.118720 | +0.118868 |
| BSS vs intercept-only | +0.070062 | — |
| ECE (5 bins) | 0.024004 | — |

## Interpretation

Read the two columns together. The headline BSS of +0.29 against climatology is mostly
D-011: on the 16 ZLB meetings the mask assigns 0.005 and is almost exactly right, while
climatology still carries 0.15–0.36 from the 2019–2020 cuts. Those 16 rows account for
about 85% of the squared-error gap. On the 23 meetings where a cut was actually possible
the model's edge over climatology shrinks to +0.06, and its edge over the intercept-only
ablation is +0.07 on the full sample. That is the true size of what the four features add.

The model also did not anticipate the first cut of the cycle: on 2024-09-18 it assigned
0.072 against climatology's 0.087. Its later cut probabilities (0.147, 0.172) rose only
after that cut was in the training set. Three cuts cannot establish forecasting skill.

The ridge scaling was corrected on September 8: the penalty is now divided by the training
sample count together with the summed data gradient. The prior implementation grew the
penalty with sample size and drove every coefficient toward zero, which made the earlier
0.070480 result indistinguishable from an intercept-only model.

This candidate does **not** clear the research sample gate: D-013 requires 30 non-ZLB
predictions and there are 23. It does **not** enable signals because D-007 requires positive
out-of-sample skill against actual prediction-market prices, which are not yet collected.

The optimizer settings are fixed in code and were not selected by searching this evaluation
period. Any later tuning must use a nested validation procedure or a separate development
period. The fitted unemployment coefficient is negative in standardized units; that sign is
not economically motivated and should be re-examined once the sample is larger.

## Reproduce

```bash
python scripts/run_fed_model_comparison.py \
  --meetings data/fomc_meetings_2019_2024.csv \
  --snapshots data/generated/fomc_feature_snapshots_2019_2024.json \
  --output data/generated/fed_walk_forward_logistic_2019_2024.json
```

`tests/test_review_5.py` recomputes the report and compares it to the checked-in JSON.
