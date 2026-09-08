"""Regression tests for Claude review 6 (market rule verification gate)."""

from datetime import UTC, datetime

from forecast_macro.market_review import (
    ContractRuleMetadata,
    ReviewStatus,
    review_market_candidates,
)
from forecast_macro.market_rules import (
    effective_resolution_source,
    identify_contract_series,
    parse_polymarket_rules,
    validate_official_rules,
    verified_rule_metadata,
)
from forecast_macro.official_sources import extract_urls, is_official_source

FETCHED = datetime(2026, 9, 8, 1, 0, tzinfo=UTC)

CORE_CPI_TEXT = (
    "This is a market about core inflation (excluding food and energy) over the 12-month "
    "period ending August 2026, before seasonal adjustment, as reported by the Bureau of "
    "Labor Statistics. The resolution source will be the BLS CPI report "
    "(https://www.bls.gov/bls/news-release/cpi.htm)."
)
UNEMPLOYMENT_TEXT = (
    "This market will resolve according to the seasonally adjusted unemployment rate (U-3) "
    "reported by the Bureau of Labor Statistics in the Employment Situation Report."
)


def _row(market_id: str, title: str, *, topic: str = "cpi", event: str = "event-1") -> dict:
    return {
        "venue": "polymarket",
        "venue_event_id": event,
        "venue_market_id": market_id,
        "title": title,
        "topic": topic,
        "outcome_labels": ["Yes", "No"],
        "outcome_token_ids": [f"{market_id}-yes", f"{market_id}-no"],
        "close_time_verified": True,
    }


def _cpi_group(month: str = "August") -> list[dict]:
    rows = [_row("low", f"Will Core CPI YoY be 2.0% or less in {month}?")]
    rows.extend(
        _row(str(value), f"Will Core CPI YoY be {value:.1f}% in {month}?") for value in (2.1, 2.2)
    )
    rows.append(_row("high", f"Will Core CPI YoY be 2.3% or more in {month}?"))
    return rows


# --- R6-H1: series identification needs positive evidence -------------------------------


def test_underspecified_cpi_contract_is_not_matched_to_model_series() -> None:
    document = parse_polymarket_rules(
        {
            "id": "vague",
            "question": "Will CPI be 0.3%?",
            "description": "Resolves per the BLS CPI report at https://www.bls.gov/cpi/.",
            "resolutionSource": "https://www.bls.gov/cpi/",
        },
        fetched_at=FETCHED,
    )
    assert identify_contract_series(document, topic="cpi") is None
    blockers = validate_official_rules(document, topic="cpi", expected_series="headline_cpi_mom_sa")
    assert "contract series could not be identified from the rule text" in blockers
    assert verified_rule_metadata(document, topic="cpi", expected_series="headline_cpi_mom_sa") is None


def test_live_polymarket_wording_identifies_core_yoy_nsa() -> None:
    document = parse_polymarket_rules(
        {
            "id": "3539692",
            "question": "Will Core CPI YoY be 2.0% or less in August?",
            "description": CORE_CPI_TEXT,
            "resolutionSource": "",
        },
        fetched_at=FETCHED,
    )
    assert identify_contract_series(document, topic="cpi") == "core_cpi_yoy_nsa"


def test_unemployment_requires_seasonal_adjustment_statement() -> None:
    explicit = parse_polymarket_rules(
        {"id": "u", "question": "Will the unemployment rate be 4.1%?", "description": UNEMPLOYMENT_TEXT},
        fetched_at=FETCHED,
    )
    assert identify_contract_series(explicit, topic="unemployment") == "unemployment_rate_sa"
    silent = parse_polymarket_rules(
        {"id": "u2", "question": "Will the unemployment rate be 4.1%?", "description": "Resolves per BLS."},
        fetched_at=FETCHED,
    )
    assert identify_contract_series(silent, topic="unemployment") is None


# --- R6-H2: review checks the official host itself --------------------------------------


def test_review_rejects_metadata_with_unofficial_source_string() -> None:
    rows = _cpi_group()
    rules = {
        str(row["venue_market_id"]): ContractRuleMetadata(
            resolution_source="BLS CPI release", rules_text_hash="sha256:abc", rules_version="v1"
        )
        for row in rows
    }
    reviews = review_market_candidates(rows, rule_metadata=rules)
    assert {review.status for review in reviews} == {ReviewStatus.RULES_REQUIRED}
    assert all(
        "resolution source is not the required official agency" in review.blockers
        for review in reviews
    )


# --- R6-H3: hash and version ignore venue updatedAt churn ---------------------------------


def test_rules_hash_is_stable_across_updated_at_changes() -> None:
    base = {"id": "m", "question": "Q?", "description": CORE_CPI_TEXT, "resolutionSource": ""}
    first = parse_polymarket_rules({**base, "updatedAt": "2026-09-07T00:00:00Z"}, fetched_at=FETCHED)
    second = parse_polymarket_rules({**base, "updatedAt": "2026-09-08T00:00:00Z"}, fetched_at=FETCHED)
    assert first.rules_text_hash == second.rules_text_hash
    assert first.rules_version == second.rules_version
    assert first.venue_updated_at != second.venue_updated_at
    changed = parse_polymarket_rules({**base, "description": CORE_CPI_TEXT + " Amended."}, fetched_at=FETCHED)
    assert changed.rules_text_hash != first.rules_text_hash
    assert first.fetched_at == FETCHED.isoformat()


# --- R6-M1: one payload level at a time ---------------------------------------------------


def test_market_and_event_fields_are_not_mixed() -> None:
    document = parse_polymarket_rules(
        {
            "id": "m",
            "question": "Will CPI be 2.1%?",
            "description": "Market-level text.",
            "events": [
                {
                    "description": "Event-level text.",
                    "resolutionSource": "https://www.bls.gov/cpi/",
                    "updatedAt": "2026-09-08T00:00:00Z",
                }
            ],
        },
        fetched_at=FETCHED,
    )
    assert document.rules_source_level == "market"
    assert document.description == "Market-level text."
    assert document.resolution_source == ""
    assert document.venue_updated_at == ""


def test_event_level_is_used_wholesale_when_market_has_no_text() -> None:
    document = parse_polymarket_rules(
        {
            "id": "m",
            "question": "Will the unemployment rate be 4.1%?",
            "events": [
                {
                    "description": UNEMPLOYMENT_TEXT,
                    "resolutionSource": "https://www.bls.gov/bls/news-release/empsit.htm",
                    "updatedAt": "2026-09-08T00:00:00Z",
                }
            ],
        },
        fetched_at=FETCHED,
    )
    assert document.rules_source_level == "event"
    assert verified_rule_metadata(document, topic="unemployment") is not None


def test_missing_text_at_both_levels_blocks() -> None:
    document = parse_polymarket_rules({"id": "m", "question": "Will CPI be 2.1%?"}, fetched_at=FETCHED)
    assert document.rules_source_level == "missing"
    assert "no rule text at market or event level" in validate_official_rules(document, topic="cpi")


# --- R6-M2: bucket parsing ----------------------------------------------------------------


def test_strict_inequality_tails_are_blocked() -> None:
    rows = [
        _row("low", "Will CPI be <2.1% in August?"),
        _row("mid", "Will CPI be 2.1% in August?"),
        _row("high", "Will CPI be >2.1% in August?"),
    ]
    reviews = review_market_candidates(rows)
    assert {review.status for review in reviews} == {ReviewStatus.REJECTED}
    assert all(
        "strict inequality tail cannot be reconciled with 0.1-point buckets" in review.blockers
        for review in reviews
    )


def test_mixed_reference_periods_are_blocked() -> None:
    rows = _cpi_group("August")
    rows[1] = _row("2.1", "Will Core CPI YoY be 2.1% in September?")
    reviews = review_market_candidates(rows)
    assert {review.status for review in reviews} == {ReviewStatus.REJECTED}
    assert all("bucket set mixes reference periods or series" in review.blockers for review in reviews)


def test_mixed_series_in_one_event_are_blocked() -> None:
    rows = _cpi_group()
    rows[1] = _row("2.1", "Will CPI YoY be 2.1% in August?")  # headline instead of core
    reviews = review_market_candidates(rows)
    assert all("bucket set mixes reference periods or series" in review.blockers for review in reviews)


def test_complete_group_with_official_rules_is_approved() -> None:
    rows = _cpi_group()
    rules = {
        str(row["venue_market_id"]): ContractRuleMetadata(
            resolution_source="https://www.bls.gov/cpi/",
            rules_text_hash="sha256:abc",
            rules_version="abc",
        )
        for row in rows
    }
    reviews = review_market_candidates(rows, rule_metadata=rules)
    assert {review.status for review in reviews} == {ReviewStatus.APPROVED}


# --- R6-M3: official URL inside the description ------------------------------------------


def test_description_url_is_accepted_only_when_official() -> None:
    document = parse_polymarket_rules(
        {"id": "3539692", "question": "Will Core CPI YoY be 2.0% or less in August?", "description": CORE_CPI_TEXT},
        fetched_at=FETCHED,
    )
    source, origin = effective_resolution_source(document, topic="cpi")
    assert origin == "description"
    assert source == "https://www.bls.gov/bls/news-release/cpi.htm"
    unofficial = parse_polymarket_rules(
        {
            "id": "x",
            "question": "Will Core CPI YoY be 2.0% or less in August?",
            "description": "Resolves per https://example.com/cpi, core 12-month, before seasonal adjustment.",
        },
        fetched_at=FETCHED,
    )
    assert effective_resolution_source(unofficial, topic="cpi") == ("", "")
    assert verified_rule_metadata(unofficial, topic="cpi") is None


def test_field_source_is_not_replaced_by_description_url() -> None:
    document = parse_polymarket_rules(
        {
            "id": "x",
            "question": "Q?",
            "description": "See https://www.bls.gov/cpi/ for details.",
            "resolutionSource": "https://example.com/blog",
        },
        fetched_at=FETCHED,
    )
    # An explicit non-official field is a red flag; the description must not rescue it.
    assert effective_resolution_source(document, topic="cpi") == ("https://example.com/blog", "")


# --- R6-L1 and host tricks ----------------------------------------------------------------


def test_official_host_requires_https_and_exact_domain() -> None:
    assert is_official_source("https://www.bls.gov/cpi/", topic="cpi")
    assert is_official_source("https://data.bls.gov/timeseries/CUUR0000SA0", topic="cpi")
    assert not is_official_source("http://www.bls.gov/cpi/", topic="cpi")
    assert not is_official_source("https://bls.gov.example.com/", topic="cpi")
    assert not is_official_source("https://bls.gov@evil.com/", topic="cpi")
    assert not is_official_source("https://www.bls.gov.evil.com/", topic="cpi")
    assert not is_official_source("https://evil.com/?u=https://www.bls.gov", topic="cpi")
    assert not is_official_source("https://www.bls.gov/cpi/", topic="fed_rate")
    assert extract_urls("see (https://www.bls.gov/cpi/). And https://bea.gov/x,") == (
        "https://www.bls.gov/cpi/",
        "https://bea.gov/x",
    )
