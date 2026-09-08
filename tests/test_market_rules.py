from forecast_macro.market_rules import (
    identify_contract_series,
    parse_polymarket_rules,
    validate_official_rules,
    verified_rule_metadata,
)


def test_polymarket_rules_are_hashed_and_verified_against_bls() -> None:
    document = parse_polymarket_rules(
        {
            "id": "3539692",
            "question": "Will Core CPI YoY be 2.0% or less in August?",
            "description": (
                "Resolves using the 12-month change in the Core CPI, before seasonal "
                "adjustment, from the Bureau of Labor Statistics CPI release."
            ),
            "resolutionSource": "https://www.bls.gov/cpi/",
            "updatedAt": "2026-09-07T12:00:00Z",
        }
    )

    assert document.rules_text_hash.startswith("sha256:")
    assert validate_official_rules(document, topic="cpi") == ()
    assert verified_rule_metadata(document, topic="cpi") is not None


def test_event_rules_are_used_as_fallback() -> None:
    document = parse_polymarket_rules(
        {
            "id": "4217153",
            "question": "Will unemployment be 3.8% or less?",
            "events": [
                {
                    "description": (
                        "Resolves from the seasonally adjusted unemployment rate in the "
                        "BLS Employment Situation release."
                    ),
                    "resolutionSource": "https://www.bls.gov/news.release/empsit.nr0.htm",
                    "updatedAt": "2026-09-08T00:00:00Z",
                }
            ],
        }
    )
    assert verified_rule_metadata(document, topic="unemployment") is not None


def test_nonofficial_source_cannot_unlock_contract() -> None:
    document = parse_polymarket_rules(
        {
            "id": "bad",
            "question": "Will CPI rise?",
            "description": "Resolves from an unofficial inflation blog.",
            "resolutionSource": "https://example.com/inflation",
            "updatedAt": "2026-09-08T00:00:00Z",
        }
    )
    assert "resolution source is not the required official agency" in validate_official_rules(
        document, topic="cpi"
    )
    assert verified_rule_metadata(document, topic="cpi") is None


def test_core_yoy_contract_cannot_unlock_headline_mom_model() -> None:
    document = parse_polymarket_rules(
        {
            "id": "core-yoy",
            "question": "Will Core CPI YoY be 2.5%?",
            "description": (
                "Resolves to the 12-month Core CPI before seasonal adjustment "
                "reported by the Bureau of Labor Statistics."
            ),
            "resolutionSource": "https://www.bls.gov/cpi/",
            "updatedAt": "2026-09-08T00:00:00Z",
        }
    )
    assert identify_contract_series(document, topic="cpi") == "core_cpi_yoy_nsa"
    blockers = validate_official_rules(
        document, topic="cpi", expected_series="headline_cpi_mom_sa"
    )
    assert any("does not match model series" in blocker for blocker in blockers)
    assert verified_rule_metadata(
        document, topic="cpi", expected_series="headline_cpi_mom_sa"
    ) is None
