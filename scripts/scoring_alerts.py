from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from forecast_macro.alerts import TOPICS, alert_files, build_scoring_alerts

SCORING_FILES = {
    "fed": Path("data/generated/fed_market_scoring.json"),
    "unemployment": Path("data/generated/unemployment_market_scoring.json"),
    "core_cpi": Path("data/generated/core_cpi_market_scoring.json"),
    "headline_cpi": Path("data/generated/headline_cpi_market_scoring.json"),
}


def committed_version(path: Path, ref: str) -> dict | None:
    """The scoring file as committed at `ref`, or None when it did not exist there."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{path.as_posix()}"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write one issue file per topic whose scoring gained newly realized outcomes"
    )
    parser.add_argument("--ref", default="HEAD", help="git ref holding the pre-run scoring files")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/alerts"))
    args = parser.parse_args()

    current = {}
    previous = {}
    for topic, path in SCORING_FILES.items():
        if topic not in TOPICS or not path.exists():
            continue
        current[topic] = json.loads(path.read_text(encoding="utf-8"))
        previous[topic] = committed_version(path, args.ref)

    run_url = ""
    if os.environ.get("GITHUB_SERVER_URL") and os.environ.get("GITHUB_RUN_ID"):
        run_url = (
            f"{os.environ['GITHUB_SERVER_URL']}/{os.environ.get('GITHUB_REPOSITORY', '')}"
            f"/actions/runs/{os.environ['GITHUB_RUN_ID']}"
        )
    alerts = build_scoring_alerts(previous, current, run_url=run_url)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, contents in alert_files(alerts).items():
        (args.output_dir / name).write_text(contents, encoding="utf-8")
    print(f"{len(alerts)} scoring alert(s) written to {args.output_dir}")
    for alert in alerts:
        print(f"- {alert.title}")


if __name__ == "__main__":
    main()
