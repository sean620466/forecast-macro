from forecast_macro.market_review import (
    ContractRuleMetadata,
    ReviewStatus,
    review_market_candidates,
)


def _row(market_id: str, title: str, topic: str = "cpi") -> dict[str, object]:
    return {
        "venue": "polymarket",
        "venue_event_id": "event-1",
        "venue_market_id": market_id,
        "title": title,
        "topic": topic,
        "outcome_labels": ["Yes", "No"],
        "outcome_token_ids": [f"{market_id}-yes", f"{market_id}-no"],
        "requires_review": True,
        "close_time_verified": True,
    }


def _complete_cpi_group() -> list[dict[str, object]]:
    rows = [_row("low", "Will Core CPI YoY be 2.0% or less in August?")]
    rows.extend(_row(str(value), f"Will Core CPI YoY be {value:.1f}% in August?") for value in [2.1, 2.2, 2.3])
    rows.append(_row("high", "Will Core CPI YoY be 2.4% or more in August?"))
    return rows


def test_complete_bucket_group_stays_locked_without_rules() -> None:
    reviews = review_market_candidates(_complete_cpi_group())
    assert {review.status for review in reviews} == {ReviewStatus.RULES_REQUIRED}
    assert all("bucket structure complete" in review.checks_passed for review in reviews)
    assert all("verified resolution source and versioned rules required" in review.blockers for review in reviews)


def test_gap_rejects_entire_event_group() -> None:
    rows = [_row("low", "Will CPI be 2.0% or less?"), _row("high", "Will CPI be 2.3% or more?")]
    reviews = review_market_candidates(rows)
    assert {review.status for review in reviews} == {ReviewStatus.REJECTED}


def test_complete_rules_allow_approval() -> None:
    rows = _complete_cpi_group()
    rules = {
        str(row["venue_market_id"]): ContractRuleMetadata(
            resolution_source="BLS CPI release",
            rules_text_hash="sha256:abc",
            rules_version="2026-09-07",
        )
        for row in rows
    }
    reviews = review_market_candidates(rows, rule_metadata=rules)
    assert {review.status for review in reviews} == {ReviewStatus.APPROVED}


def test_bad_token_mapping_never_approves() -> None:
    rows = _complete_cpi_group()
    rows[0]["outcome_token_ids"] = ["yes-only"]
    reviews = review_market_candidates(rows)
    assert reviews[0].status is ReviewStatus.RULES_REQUIRED
    assert "invalid YES/NO token mapping" in reviews[0].blockers
