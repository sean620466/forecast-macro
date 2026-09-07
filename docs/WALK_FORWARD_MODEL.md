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
| Actual cuts | 3 |
| Model Brier | 0.081278 |
| Sequential climatology Brier | 0.095612 |
| BSS vs climatology | +0.149916 |
| ECE | 0.048198 |

This clears the research comparison against sequential climatology. It does **not** enable
signals: D-007 also requires positive out-of-sample skill against actual prediction-market
prices, and that historical market-price dataset has not yet been added.

The optimizer settings are fixed in code and were not selected by searching this evaluation
period. Any later tuning must use a nested validation procedure or a separate development
period.
