# CPI YoY baselines: empirical change vs explicit base effect (task 41)

Two untuned baselines for the next published CPI year-over-year rate, both on a tenth-point
bucket grid like the Polymarket and Kalshi contracts:

- **Empirical change** (`models/core_cpi.py`): next YoY = latest YoY + a one-month change drawn
  from the history of YoY changes since 1990.
- **Base effect** (`models/cpi_base_effect.py`): next YoY = (L[t] / L[t-11]) × (1 + m[t+1]) − 1
  with the base known exactly; m[t+1] = the target calendar month's mean MoM plus a residual
  pooled from every month ("pooled"), or one draw per past year of the same month ("same_month").

`scripts/backtest_cpi_baselines.py` scores both on published NSA index levels (never revised,
so the current vintage is point-in-time) for every target month from 2000-01 to 2026-07, with
buckets ≤ latest−0.4, latest−0.3 … latest+0.3, ≥ latest+0.4. Multi-class Brier, lower is
better. No market prices are used; D-007 is untouched.

| Series | Months | Empirical change | Base effect (pooled) | Base effect (same month) | Pooled skill vs empirical | Pooled wins / empirical wins |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Core (CPILFENS) | 317 | 0.8026 | 0.8410 | 0.8531 | −4.8% | 139 / 178 |
| Headline (CPIAUCNS) | 317 | 0.8888 | 0.8132 | 0.8355 | +8.5% | 190 / 127 |

Mean probability on the realized bucket: core 0.194 (empirical) vs 0.184 (pooled); headline
0.118 vs 0.219.

## Reading

Headline NSA CPI has large, stable seasonality (energy, food), so knowing the base and the
calendar month is worth a lot: the base-effect model wins 22 of 27 years. Core MoM is smoother
and its YoY change is persistent, so the empirical YoY-change draw, centred on the latest YoY,
carries the recent run-rate that the long-history seasonal mean ignores; the base-effect model
wins only in 2011, 2012, 2021 and 2026. The 2022 spike is the worst year for every model.

Consequence: the headline comparison (Kalshi KXCPIYOY) uses the pooled base-effect model
(`headline-cpi-yoy-base-effect-pooled-mom-0.1-uncalibrated`); the core comparison keeps the
empirical-change model. Both stay uncalibrated research baselines with `signal_eligible=false`.

Result file: `data/generated/cpi_baseline_backtest.json` (rebuilt by `cpi-baselines.yml` when
either model changes).
