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

## 2019–2026 result (62 meetings, 60 scheduled)

Rerun on `data/generated/fomc_feature_snapshots_2019_2026.json` after the FOMC history was
extended through July 2026 (task 14). Same optimizer settings, same warmup of eight meetings.

| Metric | All 52 | Non-ZLB 36 |
| --- | ---: | ---: |
| Actual cuts | 6 | 6 |
| Model Brier | 0.098137 | 0.141727 |
| Sequential climatology Brier | 0.118438 | 0.145572 |
| Always-hold Brier | 0.115385 | 0.166667 |
| Intercept-only + ZLB mask Brier | 0.104385 | — |
| BSS vs climatology | +0.171 | +0.026 |
| BSS vs always-hold | +0.150 | — |
| BSS vs intercept-only | +0.060 | — |
| ECE (5 bins) | 0.064 | — |

The D-013 floor of 30 non-ZLB predictions is met for the first time (36), so
`climatology_gate_passed` is true. That is a research gate only. On the meetings where a cut
was possible the model's edge over climatology is +0.03 and over the intercept-only ablation
+0.06 on the full sample: the features add little. The three late-2025 cuts were assigned
0.31–0.36 by the heuristic baseline against climatology's 0.13–0.16, and the 2026 holds were
assigned 0.09–0.35. `signal_eligible` stays false because D-007 needs a market baseline, which
`data/generated/fed_market_comparisons/` only started accumulating on 2026-09-08.

Compared with the 2019–2024 run, skill fell (BSS vs climatology +0.29 → +0.17): the 2025–2026
period has three cuts followed by a long hold with inflation re-accelerating to 3–4% YoY,
which the four-feature model reads as mixed. It also cannot express a hike at all.

## 2015–2026 result (94 meetings, task 39)

Rerun on `data/generated/fomc_feature_snapshots_2015_2026.json`, built by the same workflow
from ALFRED vintages of the day before each meeting (the 62 overlapping meetings have
identical features to the 2019–2026 file). The extension adds the 2015–2018 tightening cycle:
nine hikes, no cuts, ZLB until December 2015.

| Metric | All 84 | Non-ZLB 68 |
| --- | ---: | ---: |
| Actual cuts / hikes | 9 / 19 | 9 / 19 |
| Model Brier | 0.095410 | 0.117789 |
| Sequential climatology Brier | 0.097330 | 0.118646 |
| Always-hold Brier | 0.107143 | 0.132353 |
| Intercept-only + ZLB mask Brier | 0.100096 | — |
| BSS vs climatology | +0.020 | +0.007 |
| BSS vs always-hold | +0.110 | — |
| BSS vs intercept-only | +0.047 | — |
| ECE (5 bins) | 0.081 | — |
| Three-way Brier (model / climatology) | 0.467 / 0.505 | — |

The skill reported on 2019–2026 does not survive the longer sample. Two effects, separable
with the per-meeting `predictions` now stored in each report:

1. **Climatology is a different baseline.** With 2015–2018 in the record the sequential
   base rate of a cut is lower and better matched to 2020–2026, so the same predictions
   earn less credit against it.
2. **More history makes the model itself worse on the same meetings.** On the 52 meetings
   both runs evaluate (2020-01 to 2026-07) the 2015-trained model's cut Brier is 0.1032 and
   its three-way Brier 0.4206, against 0.0981 and 0.3529 for the 2019-trained model. The
   2015–2018 rows tie low unemployment and rising inflation to hikes, which is the correct
   lesson for the hike model but flattens the cut model's response during 2019–2020.

By year (three-way Brier, model vs climatology, 2015-trained): the model wins clearly only
in 2020 (0.09 vs 0.15), 2022 (0.38 vs 1.03: climatology could not see the hiking cycle)
and 2026 (0.14 vs 0.18); it loses in 2016, 2021 and 2024. This is one model with two
effective regimes in 94 observations, not a stable edge.

The heuristic (`fed_baseline_backtest_window_2015_2026.json`) is worse than climatology on
this sample: Brier 0.1101 vs 0.0984, BSS −0.120, and it fails the climatology gate.

Consequences: the live comparison (`scripts/compare_fed_market.py`, model version
`fed-live-0.3-three-way-2015-uncalibrated`) trains on the 94-meeting file because a training
set chosen after seeing which period scores better would be tuning on results. The research
gate D-013 is met on numbers (68 non-ZLB, model < climatology), but the margin is one
meeting's worth of Brier. `signal_eligible` stays false; D-007 still needs the market
baseline that started accumulating on 2026-09-08.

## Three-way outcome space (D-016)

Since task 16 the report also carries `three_way_brier` (sum of squared errors over
cut/hold/hike, averaged over meetings), the matching climatology, and per-outcome `hold_brier`
and `hike_brier`. The hike probability comes from a second logistic model fitted on the
non-cut meetings (hike vs hold) and applied to the remainder after the cut model, so every
cut metric above is unchanged.

| Sample | Three-way Brier | Three-way climatology | Hike Brier | Hold Brier |
| --- | ---: | ---: | ---: | ---: |
| 2019–2024 | 0.343 | 0.556 | 0.114 | 0.161 |
| 2019–2026 | 0.353 | 0.525 | 0.087 | 0.168 |

The 2022–2023 hikes are learnable from inflation, but that is one tightening cycle. The
heuristic baseline's mirrored hike score is worse than climatology (see `EXTENDED_BACKTEST.md`).
