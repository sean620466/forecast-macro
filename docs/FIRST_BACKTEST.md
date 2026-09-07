# First Fed Baseline Backtest

This experiment evaluates the uncalibrated hand-built Fed cut model against actual 2022–2024 decisions using point-in-time ALFRED feature snapshots.

## Design

- First 8 meetings are warmup history.
- Meetings 9–24 are evaluated sequentially.
- Binary target: cut versus hold-or-hike.
- Baselines: constant 50% and sequential historical cut rate with Laplace smoothing.
- Inputs are matched by meeting date and the policy-rate snapshot must equal the recorded pre-meeting upper bound.
- Signal eligibility remains false because only 16 out-of-warmup observations are available, below D-007's minimum of 30.

## Interpretation rule

This is a diagnostic of the current heuristic, not evidence of trading advantage. A positive score versus the historical-rate baseline is not sufficient; the model must eventually beat timestamp-aligned prediction-market probabilities on at least 30 out-of-sample decisions.
