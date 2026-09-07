from __future__ import annotations

from forecast_macro.types import MarketSignal, Probability


def compare_to_market(
    model: list[Probability],
    market: dict[str, float],
    *,
    threshold: float = 0.08,
    signal_eligible: bool = False,
) -> list[MarketSignal]:
    if threshold < 0:
        raise ValueError("threshold must be non-negative")

    signals: list[MarketSignal] = []
    for estimate in model:
        if estimate.outcome not in market:
            raise KeyError(f"Missing market probability for {estimate.outcome}")
        market_probability = market[estimate.outcome]
        if not 0.0 <= market_probability <= 1.0:
            raise ValueError("market probabilities must be between 0 and 1")
        edge = estimate.probability - market_probability
        signals.append(
            MarketSignal(
                outcome=estimate.outcome,
                model_probability=estimate.probability,
                market_probability=market_probability,
                edge=edge,
                should_display=signal_eligible and abs(edge) >= threshold,
            )
        )
    return signals
