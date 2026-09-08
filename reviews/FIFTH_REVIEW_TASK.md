# Claude independent review task #5 — market rule verification

Review the latest `main` branch. Do not modify production code.

## Scope

- `src/forecast_macro/market_review.py`
- `src/forecast_macro/market_rules.py`
- `src/forecast_macro/data/polymarket.py`
- `scripts/review_macro_markets.py`
- `scripts/verify_market_rules.py`
- `.github/workflows/discover-markets.yml`
- `tests/test_market_review.py`
- `tests/test_market_rules.py`

## Required checks

1. Run `pytest -q` and `ruff check .`.
2. Verify that incomplete or non-contiguous bucket groups cannot be approved.
3. Verify that missing rule text, missing version timestamp, or a non-official source cannot unlock a contract.
4. Check URL-host validation for suffix tricks such as `bls.gov.example.com`.
5. Confirm that a venue/API failure fails closed and does not make `signal_eligible` true.
6. Inspect whether market-level and event-level rule fallback can mix mismatched rule documents.
7. Check whether `updatedAt` is a sufficiently stable rules version or whether a separate immutable snapshot timestamp is required.
8. Confirm that the 19-candidate artifact remains unapproved until the fetched rules pass every gate.

## Report format

Write the report under `reviews/` with:

- verdict: PASS, PASS WITH CHANGES, or FAIL
- Critical / High / Medium / Low findings
- exact file and function
- reproduction or failing test
- requested fix
- residual risk

Do not treat market prices as usable merely because the API returned a rule document.
