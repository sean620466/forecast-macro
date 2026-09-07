# Claude Review #2 — Backtest Foundation

## Verdict

PASS WITH CHANGES. No Critical findings remained. Claude identified two High risks: outcome-aware purging was absent, and vintage enforcement was not end-to-end.

## Accepted findings

- H-1: training rows must be purged when their outcomes were not known by the test forecast cutoff.
- H-2: vintage provenance must be enforced at runtime, not only documented.
- M-1: decimal calibration-bin boundaries need stable integer indexing.
- M-2: Brier score needs baseline and skill-score comparison.
- M-3: three-way FOMC labels need an explicit mapping to the binary baseline model.
- M-4: unemployment inputs used for a change must use the same vintage.
- M-5: data released exactly at the forecast cutoff is not considered safely available.
- M-6: partial final test windows require an explicit option.
- L-1: signal eligibility and force-display semantics must be named separately.
- L-3: timestamps must be timezone-aware.

## Note

Claude could not run pytest or Ruff because of its network environment. ChatGPT reproduced the findings, implemented accepted changes, and ran the complete local suite.
