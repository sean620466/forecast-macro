from forecast_macro.market_discovery import (
    MacroTopic,
    classify_macro_title,
    kalshi_candidates,
    polymarket_candidates,
)


def test_classification_requires_topic_words() -> None:
    assert classify_macro_title("Will the Fed cut interest rates?")[0] is MacroTopic.FED_RATE
    assert classify_macro_title("What will CPI inflation be?")[0] is MacroTopic.CPI
    assert classify_macro_title("Who will win the election?") is None


def test_kalshi_discovery_keeps_candidates_for_review() -> None:
    candidates = kalshi_candidates(
        {
            "markets": [
                {
                    "ticker": "KXFED-TEST",
                    "event_ticker": "KXFED",
                    "title": "Will the Fed cut interest rates?",
                    "status": "open",
                    "close_time": "2026-10-28T18:00:00Z",
                },
                {"ticker": "OTHER", "title": "Election winner", "status": "open"},
            ]
        }
    )

    assert len(candidates) == 1
    assert candidates[0].topic is MacroTopic.FED_RATE
    assert candidates[0].requires_review is True


def test_polymarket_requires_complete_token_mapping() -> None:
    candidates = polymarket_candidates(
        {
            "markets": [
                {
                    "id": "123",
                    "question": "Will CPI inflation exceed 3%?",
                    "active": True,
                    "closed": False,
                    "endDate": "2026-10-01T12:00:00Z",
                    "outcomes": '["Yes", "No"]',
                    "clobTokenIds": '["yes-token", "no-token"]',
                },
                {
                    "id": "bad",
                    "question": "Will GDP decline?",
                    "active": True,
                    "outcomes": '["Yes", "No"]',
                    "clobTokenIds": '["only-one"]',
                },
            ]
        }
    )

    assert len(candidates) == 1
    assert candidates[0].topic is MacroTopic.CPI
    assert candidates[0].outcome_token_ids == ("yes-token", "no-token")
