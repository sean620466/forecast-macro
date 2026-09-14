"""Realized FOMC decisions for the D-007 scoring loop (task 48).

`comparison_scoring` labels a meeting only when its decision is in the meeting history CSV.
That file is transcribed by hand and doubles as a regression fixture (its feature snapshots
are checked in), so a decision made on Wednesday would not be scored until a person edited
the file. This module gives the daily workflow its own label source:

- the decision press release (`monetary<YYYYMMDD>a.htm`, the D-002 source every history row
  already cites) is fetched and its decision sentence parsed into the new target range;
- the row is appended to a bot-owned file with the history schema
  (`data/generated/fomc_decisions.csv`) after the same validation `load_fomc_history` applies;
- the scorer merges that file with the history, so the meeting is scored on the next run.

Training data is untouched: the live model keeps fitting on the history CSV and its
snapshots (extending those stays a deliberate, reviewed step). Nothing here touches
`signal_eligible` (D-012).
"""
from __future__ import annotations

import csv
import html
import re
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

from forecast_macro.datasets import HistoricalFomcRow, load_fomc_history
from forecast_macro.fomc import RateDecision, label_rate_decision
from forecast_macro.release_schedule import ScheduledRelease

PRESS_RELEASE_URL = "https://www.federalreserve.gov/newsevents/pressreleases/monetary{stamp}a.htm"
DEFAULT_REALIZED_PATH = Path("data/generated/fomc_decisions.csv")
HISTORY_FIELDS = (
    "meeting_date",
    "decision_time_local",
    "timezone",
    "upper_before",
    "upper_after",
    "change_bps",
    "decision",
    "event_type",
    "source",
)

# Target-range bounds as the Board writes them: "3-3/4", "1/4", "0", occasionally "5.25".
_BOUND = r"(?:\d+-\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)"
_RANGE = rf"(?P<lower>{_BOUND})\s+to\s+(?P<upper>{_BOUND})\s+percent"
# The decision sentence. Dissents say "preferred to maintain the target range at X to Y
# percent", so the match is anchored on "the Committee decided to" and never on a bare range.
_DECISION = re.compile(
    r"the Committee (?:today )?decided to (?P<verb>maintain|keep|lower|reduce|raise|increase) "
    r"the target range for the federal funds rate "
    rf"(?:at|to|by\s+{_BOUND}\s+percentage\s+points?\s+to)\s+{_RANGE}",
    re.IGNORECASE,
)
# 2009–2015 wording: "the current 0 to 1/4 percent target range for the federal funds rate
# remains appropriate" (a hold).
_REAFFIRMED = re.compile(
    rf"the current {_RANGE} target range for the federal funds rate remains appropriate",
    re.IGNORECASE,
)
_VERB_DECISION = {
    "maintain": RateDecision.HOLD,
    "keep": RateDecision.HOLD,
    "lower": RateDecision.CUT,
    "reduce": RateDecision.CUT,
    "raise": RateDecision.HIKE,
    "increase": RateDecision.HIKE,
}


_DASHES = str.maketrans({c: "-" for c in "\u2010\u2011\u2012\u2013"})


class StatementUnavailable(RuntimeError):
    """The press release could not be fetched (not published yet, blocked, or a transport error)."""


@dataclass(frozen=True)
class ParsedStatement:
    lower: float
    upper: float
    decision: RateDecision


def press_release_url(meeting_date: date) -> str:
    return PRESS_RELEASE_URL.format(stamp=meeting_date.strftime("%Y%m%d"))


def _bound_to_float(text: str) -> float:
    whole, sep, fraction = text.partition("-")
    if not sep and "/" in whole:
        whole, fraction = "0", whole
    value = float(whole)
    if fraction:
        numerator, denominator = fraction.split("/")
        value += float(numerator) / float(denominator)
    return value


def statement_text(document: str) -> str:
    """Plain text of a press-release page: tags removed, entities decoded, spaces collapsed."""
    without_tags = re.sub(r"<[^>]+>", " ", document)
    # The Board writes "3‑1/2" with a non-breaking hyphen (U+2011) on some pages.
    text = html.unescape(without_tags).translate(_DASHES)
    return re.sub(r"\s+", " ", text).strip()


def parse_statement(document: str) -> ParsedStatement:
    """The target range the Committee decided on, read from the decision sentence.

    Every decision sentence in the page must agree (there is normally exactly one; dissents
    use "preferred to" and are ignored). Raises ValueError when no decision sentence is
    found, when sentences disagree, or when the range is not a quarter point wide.
    """
    text = statement_text(document)
    found: list[ParsedStatement] = []
    for match in _DECISION.finditer(text):
        lower, upper = (_bound_to_float(match.group(name)) for name in ("lower", "upper"))
        found.append(ParsedStatement(lower, upper, _VERB_DECISION[match.group("verb").lower()]))
    for match in _REAFFIRMED.finditer(text):
        lower, upper = (_bound_to_float(match.group(name)) for name in ("lower", "upper"))
        found.append(ParsedStatement(lower, upper, RateDecision.HOLD))
    if not found:
        raise ValueError("no FOMC decision sentence with a target range found in the statement")
    if len({(item.lower, item.upper, item.decision) for item in found}) != 1:
        raise ValueError(f"statement decision sentences disagree: {found}")
    parsed = found[0]
    if abs((parsed.upper - parsed.lower) - 0.25) > 1e-9:
        raise ValueError(f"target range {parsed.lower}–{parsed.upper} is not a quarter point wide")
    return parsed


def fetch_statement(url: str, *, timeout: float = 20.0, max_retries: int = 3) -> str:
    """Read-only GET of the decision press release. Raises StatementUnavailable on any failure."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; forecast-macro/0.1; +https://github.com)"}
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        except httpx.TransportError as exc:
            last_error = exc
            continue
        if response.status_code == 200:
            return response.text
        last_error = RuntimeError(f"HTTP {response.status_code} for {url}")
        if response.status_code < 500 and response.status_code != 429:
            break
        if attempt < max_retries:
            time.sleep(min(2**attempt, 8))
    raise StatementUnavailable(str(last_error))


def realized_decision_row(
    meeting: ScheduledRelease, *, upper_before: float, statement: str, source: str | None = None
) -> dict[str, str]:
    """One history-schema row for a scheduled meeting, labelled from its statement text.

    The verb in the decision sentence ("maintain"/"lower"/"raise") must agree with the change
    implied by `upper_before`, which is an independent check on both the parse and the
    history the row is appended to.
    """
    parsed = parse_statement(statement)
    decision = label_rate_decision(upper_before=upper_before, upper_after=parsed.upper)
    if decision is not parsed.decision:
        raise ValueError(
            f"statement says {parsed.decision.value} but the range moved {upper_before} -> "
            f"{parsed.upper} ({decision.value}); check upper_before"
        )
    meeting_date = meeting.release_at.date()
    return {
        "meeting_date": meeting_date.isoformat(),
        "decision_time_local": meeting.release_at.strftime("%H:%M"),
        "timezone": "America/New_York",
        "upper_before": f"{upper_before:.2f}",
        "upper_after": f"{parsed.upper:.2f}",
        "change_bps": str(round((parsed.upper - upper_before) * 100)),
        "decision": decision.value,
        "event_type": "scheduled",
        "source": source or press_release_url(meeting_date),
    }


def load_realized_decisions(path: Path) -> list[HistoricalFomcRow]:
    """Rows of the bot-owned decisions file; empty when the file is missing or header-only."""
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        if sum(1 for _ in csv.DictReader(handle)) == 0:
            return []
    return load_fomc_history(path)


def merge_decisions(
    history: Sequence[HistoricalFomcRow], realized: Sequence[HistoricalFomcRow]
) -> list[HistoricalFomcRow]:
    """History plus the realized rows it does not have yet, validated for agreement and continuity.

    A realized row for a meeting the history already carries must match it exactly (the
    history is the reviewed record); rows after the history's last meeting are appended and
    must continue its target range.
    """
    by_date = {row.meeting_at.date(): row for row in history}
    merged = list(history)
    last = merged[-1] if merged else None
    for row in sorted(realized, key=lambda item: item.meeting_at):
        existing = by_date.get(row.meeting_at.date())
        if existing is not None:
            if existing != row:
                raise ValueError(f"realized decision for {row.meeting_at.date()} disagrees with the history")
            continue
        if last is not None and row.meeting_at <= last.meeting_at:
            raise ValueError(f"realized decision {row.meeting_at.date()} predates the history's last meeting")
        if last is not None and row.upper_before != last.upper_after:
            raise ValueError(f"target range discontinuity before {row.meeting_at.date()}")
        merged.append(row)
        last = row
    return merged


def pending_meetings(
    schedule: Iterable[ScheduledRelease],
    *,
    known: Sequence[HistoricalFomcRow],
    as_of: datetime,
) -> list[ScheduledRelease]:
    """Scheduled FOMC decisions already announced (per the calendar) that have no label yet."""
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    known_dates = {row.meeting_at.date() for row in known}
    last_known = max((row.meeting_at for row in known), default=None)
    return sorted(
        (
            row
            for row in schedule
            if row.series == "fomc"
            and row.release_at <= as_of
            and row.release_at.date() not in known_dates
            and (last_known is None or row.release_at > last_known)
        ),
        key=lambda row: row.release_at,
    )


def append_decision_row(path: Path, row: dict[str, str]) -> list[HistoricalFomcRow]:
    """Append one row and return the file's rows; the file is left unchanged if validation fails."""
    existing: list[dict[str, str]] = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as handle:
            existing = list(csv.DictReader(handle))
    candidate = path.with_name(path.name + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with candidate.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HISTORY_FIELDS, lineterminator="\n")
        writer.writeheader()
        for item in [*existing, row]:
            writer.writerow({field: item[field] for field in HISTORY_FIELDS})
    try:
        rows = load_fomc_history(candidate)
    except ValueError:
        candidate.unlink()
        raise
    candidate.replace(path)
    return rows


def overdue(meeting: ScheduledRelease, *, as_of: datetime, grace: timedelta) -> bool:
    """True once a decision has been out long enough that a missing statement is an error."""
    return as_of - meeting.release_at > grace
