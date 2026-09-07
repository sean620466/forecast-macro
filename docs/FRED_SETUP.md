# FRED API Setup

## Obtain a key

1. Sign in or register at `https://fredaccount.stlouisfed.org/`.
2. Open the API Keys area and request a distinct key for FORECAST MACRO.
3. Never place the key in `.env.example`, source code, an issue, or a chat transcript.

## Add the GitHub secret

In `sean620466/forecast-macro`, open **Settings → Secrets and variables → Actions → New repository secret**.

- Name: `FRED_API_KEY`
- Secret: the issued key

Then open **Actions → Build historical snapshots → Run workflow**. The workflow stores the resulting JSON as a downloadable GitHub Actions artifact; it does not commit generated data automatically.

## Local use

Set `FRED_API_KEY` in the shell environment and run:

```bash
python scripts/build_fomc_snapshots.py \
  --meetings data/fomc_meetings_2022_2024.csv \
  --output artifacts/fomc_feature_snapshots.json
```

The key remains outside the repository.
