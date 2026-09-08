"""Task 07: outcome time from the official release calendar (R5-H3, D-009)."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from forecast_macro.market_discovery import polymarket_candidates
from forecast_macro.release_schedule import (
    DEFAULT_SCHEDULE_PATH,
    load_release_schedule,
    parse_meeting_statement,
    parse_release_statement,
    verify_close_time,
)

ROOT = Path(__file__).parents[1]
ET = ZoneInfo("America/New_York")
SCHEDULE = load_release_schedule()

UNEMPLOYMENT_TEXT = (
    "The relevant data release is scheduled for October 2, 2026, at 8:30 AM ET. This market "
    "resolves per the seasonally adjusted unemployment rate from the BLS."
)
CPI_TEXT = (
    "The resolution source for this market will be the BLS Consumer Price Index report released "
    "for August 2026, currently scheduled to be released on September 11, 2026, at 8:30 AM ET."
)


def test_checked_in_schedule_loads_with_provenance() -> None:
    assert DEFAULT_SCHEDULE_PATH == ROOT / "data" / "release_schedule.csv"
    assert {row.series for row in SCHEDULE} == {"cpi", "employment_situation", "fomc"}
    assert all(row.source_url.startswith("https://www.") for row in SCHEDULE)
    assert all(row.fetched_at for row in SCHEDULE)
    assert all(row.release_at.tzinfo is not None for row in SCHEDULE)


def test_release_statement_parses_to_eastern_time() -> None:
    parsed = parse_release_statement(UNEMPLOYMENT_TEXT)
    assert parsed == datetime(2026, 10, 2, 8, 30, tzinfo=ET)
    assert parsed.astimezone(UTC) == datetime(2026, 10, 2, 12, 30, tzinfo=UTC)
    assert parse_release_statement("Sep. 11, 2026 at 8:30 a.m. ET") == datetime(
        2026, 9, 11, 8, 30, tzinfo=ET
    )
    assert parse_release_statement("resolves at 2:00 PM ET on the meeting day") is None


def test_dst_boundaries_keep_wall_clock_time() -> None:
    # 2026-03-06 (EST, UTC-5) and 2026-04-03 (EDT, UTC-4) are both 08:30 wall clock.
    march = next(r for r in SCHEDULE if r.series == "employment_situation" and r.reference_period == "2026-02")
    april = next(r for r in SCHEDULE if r.series == "employment_situation" and r.reference_period == "2026-03")
    assert march.release_at.astimezone(UTC).hour == 13
    assert april.release_at.astimezone(UTC).hour == 12


def test_unemployment_contract_verifies_with_venue_close_before_release() -> None:
    # Live Polymarket endDate on 2026-09-07 was "2026-10-02T08:30:00Z": before the 12:30Z release.
    result = verify_close_time(
        topic="unemployment",
        rule_text=UNEMPLOYMENT_TEXT,
        venue_close_raw="2026-10-02T08:30:00Z",
        schedule=SCHEDULE,
    )
    assert result.verified is True
    assert result.outcome_at == datetime(2026, 10, 2, 8, 30, tzinfo=ET)
    assert result.closes_at == datetime(2026, 10, 2, 8, 30, tzinfo=UTC)
    assert result.venue_close_interpretation == "before_release"


def test_venue_close_after_official_release_is_refused() -> None:
    result = verify_close_time(
        topic="unemployment",
        rule_text=UNEMPLOYMENT_TEXT,
        venue_close_raw="2026-10-02T13:00:00Z",
        schedule=SCHEDULE,
    )
    assert result.verified is False
    assert result.outcome_at is not None
    assert any("after the official release" in blocker for blocker in result.blockers)


def test_statement_missing_or_off_calendar_fails_closed() -> None:
    missing = verify_close_time(
        topic="cpi", rule_text="Resolves per BLS.", venue_close_raw="2026-09-11T03:59:00Z", schedule=SCHEDULE
    )
    assert missing.verified is False and missing.outcome_at is None
    off_calendar = verify_close_time(
        topic="cpi",
        rule_text="scheduled to be released on September 12, 2026, at 8:30 AM ET",
        venue_close_raw="2026-09-11T03:59:00Z",
        schedule=SCHEDULE,
    )
    assert off_calendar.verified is False
    assert any("not on the official cpi calendar" in blocker for blocker in off_calendar.blockers)
    no_venue = verify_close_time(topic="cpi", rule_text=CPI_TEXT, venue_close_raw=None, schedule=SCHEDULE)
    assert no_venue.verified is False and no_venue.outcome_at is not None


def test_implausibly_early_venue_close_is_refused() -> None:
    result = verify_close_time(
        topic="cpi",
        rule_text=CPI_TEXT,
        venue_close_raw=(datetime(2026, 9, 11, 12, 30, tzinfo=UTC) - timedelta(days=3)).isoformat(),
        schedule=SCHEDULE,
    )
    assert result.verified is False


def test_fomc_meeting_statement_uses_decision_time() -> None:
    assert parse_meeting_statement("following the Fed's Sep 16, 2026 meeting") == date(2026, 9, 16)
    result = verify_close_time(
        topic="fed_rate",
        rule_text="Will the upper bound be above 4.25% following the Fed's September 16, 2026 meeting?",
        venue_close_raw="2026-09-16T17:55:00Z",
        schedule=SCHEDULE,
    )
    assert result.verified is True
    assert result.outcome_at == datetime(2026, 9, 16, 14, 0, tzinfo=ET)


def test_polymarket_discovery_keeps_raw_close_for_reconciliation() -> None:
    candidates = polymarket_candidates(
        {
            "markets": [
                {
                    "id": "1",
                    "question": "Will CPI inflation exceed 3%?",
                    "active": True,
                    "closed": False,
                    "endDate": "2026-10-01T12:00:00Z",
                    "outcomes": '["Yes", "No"]',
                    "clobTokenIds": '["a", "b"]',
                }
            ]
        }
    )
    assert candidates[0].closes_at is None
    assert candidates[0].close_time_verified is False
    assert candidates[0].venue_close_raw == "2026-10-01T12:00:00Z"


def test_schedule_rejects_non_eastern_rows(tmp_path: Path) -> None:
    bad = tmp_path / "s.csv"
    bad.write_text(
        "series,reference_period,release_date,release_time_local,timezone,source_url,fetched_at\n"
        "cpi,2026-08,2026-09-11,12:30,UTC,https://www.bls.gov/x,2026-09-08T00:00:00+00:00\n"
    )
    with pytest.raises(ValueError, match="America/New_York"):
        load_release_schedule(bad)
