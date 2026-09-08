# Walk-forward Fed model candidate

The fixed-form heuristic failed the extended 2019–2024 test. This candidate replaces it
with a deterministic ridge-logistic model using the same four point-in-time features:
CPI YoY, unemployment, three-month unemployment change, and the target-range upper bound.

For every prediction, scaling and coefficients are fitted again using only earlier FOMC
decisions. No future observation or outcome enters training.

## Scheduled-meeting result

| Metric | Value |
| --- | ---: |
| Out-of-sample predictions | 39 |
| Non-ZLB predictions | 23 |
| Actual cuts | 3 |
| Model Brier | 0.067791 |
| Sequential climatology Brier | 0.095612 |
| BSS vs climatology | +0.290978 |
| ECE | 0.024004 |

This beats sequential climatology but does **not** clear the research sample gate: D-013
requires 30 non-ZLB predictions and there are 23. It also does **not** enable signals because
D-007 requires positive out-of-sample skill against actual prediction-market prices.

The optimizer settings are fixed in code and were not selected by searching this evaluation
period. Any later tuning must use a nested validation procedure or a separate development
period.

The September 8 review corrected ridge-gradient scaling: the penalty is now divided by the
training sample count together with the summed data gradient. The prior implementation made
the penalty effectively grow with sample size and drove fitted coefficients toward zero.
The figures above are the post-correction walk-forward results.
