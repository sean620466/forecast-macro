from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Official publication calendars, transcribed into data/release_schedule.csv with the source
# URL and fetch time. BLS refuses scripted requests, so the CSV is refreshed by hand from the
# schedule pages and every row carries its provenance (D-002, D-009).

DEFAULT_SCHEDULE_PATH = Path(__file__).resolve().parents[2] / "data" / "release_schedule.csv"

TOPIC_SERIES: dict[str, str] = {
    "cpi": "cpi",
    "unemployment": "employment_situation",
    "fed_rate": "fomc",
}

_MONTHS = {
    name.lower(): index
    for index, name in enumerate(
        (
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ),
        start=1,
    )
}
_MONTH_ALTERNATION = "|".join(
    sorted({*(m for m in _MONTHS), *(m[:3] for m in _MONTHS), "sept"}, key=len, reverse=True)
)
# "released on October 2, 2026, at 8:30 AM ET" / "Sep. 11, 2026 at 8:30 a.m. ET"
_RELEASE_STATEMENT = re.compile(
    rf"\b(?P<month>{_MONTH_ALTERNATION})\.?\s+(?P<day>\d{{1,2}}),?\s+(?P<year>\d{{4}})"
    rf"[,\s]*(?:at\s+)?(?P<hour>\d{{1,2}})(?::(?P<minute>\d{{2}}))?\s*(?P<ampm>a\.?m\.?|p\.?m\.?)"
    rf"\s*(?P<zone>ET|EST|EDT|Eastern)\b",
    re.IGNORECASE,
)
# "following the Fed's Apr 28, 2027 meeting" / "September 16, 2026 FOMC meeting"
_MEETING_STATEMENT = re.compile(
    rf"\b(?P<month>{_MONTH_ALTERNATION})\.?\s+(?P<day>\d{{1,2}}),?\s+(?P<year>\d{{4}})\s+(?:fomc\s+)?meeting\b",
    re.IGNORECASE,
)
EASTERN = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class ScheduledRelease:
    series: str
    reference_period: str
    release_at: datetime  # timezone-aware, America/New_York
    source_url: str
    fetched_at: str


@dataclass(frozen=True)
class CloseTimeVerification:
    verified: bool
    outcome_at: datetime | None
    closes_at: datetime | None
    venue_close_interpretation: str  # "utc" | "before_release" | "" (unverified)
    blockers: tuple[str, ...]


def load_release_schedule(path: str | Path = DEFAULT_SCHEDULE_PATH) -> list[ScheduledRelease]:
    rows: list[ScheduledRelease] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            if raw["timezone"] != "America/New_York":
                raise ValueError("release schedule rows must be recorded in America/New_York")
            release_at = datetime.combine(
                date.fromisoformat(raw["release_date"]),
                time.fromisoformat(raw["release_time_local"]),
                tzinfo=EASTERN,
            )
            if not raw["source_url"].startswith("https://"):
                raise ValueError("release schedule rows require an https source URL")
            rows.append(
                ScheduledRelease(
                    series=raw["series"],
                    reference_period=raw["reference_period"],
                    release_at=release_at,
                    source_url=raw["source_url"],
                    fetched_at=raw["fetched_at"],
                )
            )
    if not rows:
        raise ValueError("release schedule is empty")
    keys = [(row.series, row.reference_period) for row in rows]
    if len(set(keys)) != len(keys):
        raise ValueError("release schedule has duplicate series/period rows")
    return rows


def _month_number(token: str) -> int:
    token = token.lower().rstrip(".")
    if token == "sept":
        return 9
    for name, index in _MONTHS.items():
        if name == token or name[:3] == token:
            return index
    raise ValueError(f"unknown month token {token!r}")


def parse_release_statement(text: str) -> datetime | None:
    """Return the first 'Month D, YYYY at H:MM AM ET' statement as an Eastern datetime."""
    match = _RELEASE_STATEMENT.search(text)
    if not match:
        return None
    hour = int(match.group("hour")) % 12
    if match.group("ampm").lower().startswith("p"):
        hour += 12
    minute = int(match.group("minute") or 0)
    return datetime(
        int(match.group("year")),
        _month_number(match.group("month")),
        int(match.group("day")),
        hour,
        minute,
        tzinfo=EASTERN,
    )


def parse_meeting_statement(text: str) -> date | None:
    match = _MEETING_STATEMENT.search(text)
    if not match:
        return None
    return date(int(match.group("year")), _month_number(match.group("month")), int(match.group("day")))


def find_release(
    schedule: list[ScheduledRelease], *, series: str, release_at: datetime
) -> ScheduledRelease | None:
    for row in schedule:
        if row.series == series and row.release_at == release_at:
            return row
    return None


def verify_close_time(
    *,
    topic: str,
    rule_text: str,
    venue_close_raw: str | None,
    schedule: list[ScheduledRelease],
    max_venue_offset: timedelta = timedelta(days=2),
) -> CloseTimeVerification:
    """Derive outcome_at from the official calendar and reconcile the venue close time.

    The contract text must state a release (or meeting) date that appears in the official
    schedule; that official time becomes outcome_at. The venue's close is accepted only when
    it does not fall after outcome_at. A venue close before the release is a legitimate early
    close and is kept as closes_at; a close after the release would allow trading on a known
    outcome and is refused (R5-H3, D-009).
    """
    series = TOPIC_SERIES.get(topic)
    if series is None:
        return CloseTimeVerification(False, None, None, "", ("no official calendar for topic",))

    if series == "fomc":
        meeting_date = parse_meeting_statement(rule_text)
        stated = (
            datetime.combine(meeting_date, time(14, 0), tzinfo=EASTERN) if meeting_date else None
        )
    else:
        stated = parse_release_statement(rule_text)
    if stated is None:
        return CloseTimeVerification(
            False, None, None, "", ("contract text does not state the official release time",)
        )
    official = find_release(schedule, series=series, release_at=stated)
    if official is None:
        return CloseTimeVerification(
            False,
            None,
            None,
            "",
            (f"stated release {stated.isoformat()} is not on the official {series} calendar",),
        )
    outcome_at = official.release_at

    if not venue_close_raw:
        return CloseTimeVerification(
            False, outcome_at, None, "", ("venue close time is missing",)
        )
    venue_close = datetime.fromisoformat(str(venue_close_raw))
    if venue_close.tzinfo is None:
        return CloseTimeVerification(
            False, outcome_at, None, "", ("venue close time is not timezone-aware",)
        )
    if venue_close > outcome_at:
        return CloseTimeVerification(
            False,
            outcome_at,
            None,
            "",
            ("venue close time falls after the official release; trading would see the outcome",),
        )
    if outcome_at - venue_close > max_venue_offset:
        return CloseTimeVerification(
            False,
            outcome_at,
            None,
            "",
            ("venue close time is implausibly far before the official release",),
        )
    interpretation = "utc" if venue_close == outcome_at else "before_release"
    return CloseTimeVerification(True, outcome_at, venue_close, interpretation, ())
