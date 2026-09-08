from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from forecast_macro.release_schedule import load_release_schedule
from forecast_macro.schedule_coverage import coverage, shortfalls


def main() -> None:
    parser = argparse.ArgumentParser(description="Fail while the transcribed release calendar still has time to be extended")
    parser.add_argument("--minimum-days", type=int, default=45)
    args = parser.parse_args()
    reports = coverage(load_release_schedule(), as_of=datetime.now(UTC), minimum_days=args.minimum_days)
    for report in reports:
        print(f"{report.series:22s} last {str(report.last_release_at)[:10]:10s} {report.days_ahead} days ahead {'ok' if report.ok else 'SHORT'}")
    problems = shortfalls(reports)
    if problems:
        print("\n".join(problems))
        print("Transcribe the next months from the official calendars; procedure in docs/RELEASE_SCHEDULE.md")
        sys.exit(1)


if __name__ == "__main__":
    main()
