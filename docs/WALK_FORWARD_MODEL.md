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
| Model Brier | 0.070480 |
| Sequential climatology Brier | 0.095612 |
| BSS vs climatology | +0.262851 |
| ECE | 0.028364 |

This beats sequential climatology but does **not** clear the research sample gate: D-013
requires 30 non-ZLB predictions and there are 23. It also does **not** enable signals because
D-007 requires positive out-of-sample skill against actual prediction-market prices.

The optimizer settings are fixed in code and were not selected by searching this evaluation
period. Any later tuning must use a nested validation procedure or a separate development
period.
