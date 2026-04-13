"""SynthesisAgent — orchestrates all agents and produces composite signal.

This is the main entry point for the multi-agent reasoning engine.
It runs all specialized agents, weighs their outputs, and produces
a single actionable signal with confidence and reasoning.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from app.ai.agents.base import AgentSignal, BaseAgent, CompositeSignal
from app.ai.agents.sentiment_agent import SentimentAgent
from app.ai.agents.technical_agent import TechnicalAgent
from app.ai.agents.onchain_agent import OnChainAgent
from app.ai.agents.regulatory_agent import RegulatoryAgent
from app.ai.signal_ensemble import SignalEnsemble, _ensemble as _module_ensemble

logger = logging.getLogger(__name__)

# Agent weights for composite score (fallback when ensemble disabled)
AGENT_WEIGHTS = {
    "sentiment": 0.25,
    "technical": 0.30,
    "onchain": 0.20,
    "regulatory": 0.15,
    "anomaly": 0.10,
}


class SynthesisAgent:
    """Orchestrates all agents and produces composite market signal."""

    def __init__(self):
        self.agents: list[BaseAgent] = [
            SentimentAgent(),
            TechnicalAgent(),
            OnChainAgent(),
            RegulatoryAgent(),
        ]
        self.ensemble: SignalEnsemble = _module_ensemble

    async def analyze(self, symbol: str = "BTC/USDT", **kwargs) -> CompositeSignal:
        """Run all agents in parallel and synthesize results."""
        # Run all agents concurrently
        tasks = [agent.analyze(symbol, **kwargs) for agent in self.agents]
        results: list[AgentSignal] = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out errors
        signals: list[AgentSignal] = []
        for r in results:
            if isinstance(r, AgentSignal):
                signals.append(r)
            elif isinstance(r, Exception):
                logger.warning("Agent failed: %s", r)

        if not signals:
            return CompositeSignal(
                symbol=symbol,
                overall_signal="neutral",
                overall_score=0.0,
                confidence=0.0,
                agent_signals=[],
                reasoning="No agent data available",
                risk_factors=["No data"],
                key_drivers=[],
            )

        # Use adaptive ensemble when feature flag is enabled
        from app.feature_flags import is_enabled
        use_ensemble = is_enabled("ml_ensemble")

        if use_ensemble:
            ensemble_result = self.ensemble.combine_signals(signals)
            composite_score = ensemble_result["score"]
            confidence = ensemble_result["confidence"]
            overall = ensemble_result["signal"]
            weights_info = f" (adaptive weights: {ensemble_result['weights_used']})"
        else:
            # Fall back to fixed weights (existing logic)
            weighted_score = 0.0
            total_weight = 0.0
            for sig in signals:
                w = AGENT_WEIGHTS.get(sig.agent_name, 0.1)
                effective_weight = w * sig.confidence
                weighted_score += sig.score * effective_weight
                total_weight += effective_weight

            composite_score = weighted_score / total_weight if total_weight > 0 else 0.0

            if composite_score >= 0.5:
                overall = "strong_buy"
            elif composite_score >= 0.2:
                overall = "buy"
            elif composite_score <= -0.5:
                overall = "strong_sell"
            elif composite_score <= -0.2:
                overall = "sell"
            else:
                overall = "neutral"

            avg_confidence = sum(s.confidence for s in signals) / len(signals)
            bullish = sum(1 for s in signals if s.score > 0.1)
            bearish = sum(1 for s in signals if s.score < -0.1)
            agreement = max(bullish, bearish) / len(signals) if signals else 0
            confidence = avg_confidence * (0.5 + 0.5 * agreement)
            weights_info = " (fixed weights)"

        # Extract key drivers (agents with strongest signals)
        sorted_by_impact = sorted(signals, key=lambda s: abs(s.score), reverse=True)
        key_drivers = [
            f"{s.agent_name}: {s.signal} ({s.score:+.2f})"
            for s in sorted_by_impact[:3]
        ]

        # Risk factors
        risk_factors = []
        for sig in signals:
            if sig.signal == "bearish" and sig.confidence > 0.3:
                risk_factors.append(f"{sig.agent_name}: {sig.reasoning}")
        if not risk_factors:
            risk_factors.append("No significant risks detected")

        # Generate reasoning
        agent_summary = ", ".join(
            f"{s.agent_name}={s.signal}" for s in signals
        )
        reasoning = (
            f"Composite signal based on {len(signals)} agents ({agent_summary}). "
            f"Weighted score: {composite_score:+.3f}{weights_info}."
        )

        return CompositeSignal(
            symbol=symbol,
            overall_signal=overall,
            overall_score=round(composite_score, 4),
            confidence=round(confidence, 3),
            agent_signals=signals,
            reasoning=reasoning,
            risk_factors=risk_factors,
            key_drivers=key_drivers,
        )


# Convenience function
async def get_market_signal(symbol: str = "BTC/USDT") -> dict:
    """Get composite market signal for a symbol. Returns dict."""
    engine = SynthesisAgent()
    result = await engine.analyze(symbol)

    # Store the signal score in signal_scores table
    try:
        from app.ai.backtesting import store_composite_signal
        store_composite_signal(result.to_dict())
    except Exception as e:
        logger.debug("Failed to store signal score: %s", e)

    return result.to_dict()
