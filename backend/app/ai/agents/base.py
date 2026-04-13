"""Base agent interface and shared utilities."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentSignal:
    """Output from a single agent's analysis."""
    agent_name: str
    symbol: str
    signal: str  # "bullish", "bearish", "neutral", "alert"
    confidence: float  # 0.0 to 1.0
    score: float  # -1.0 to 1.0
    reasoning: str
    data: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class CompositeSignal:
    """Combined output from all agents via SynthesisAgent."""
    symbol: str
    overall_signal: str  # "strong_buy", "buy", "neutral", "sell", "strong_sell"
    overall_score: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    agent_signals: list[AgentSignal]
    reasoning: str
    risk_factors: list[str]
    key_drivers: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "overall_signal": self.overall_signal,
            "overall_score": self.overall_score,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "risk_factors": self.risk_factors,
            "key_drivers": self.key_drivers,
            "timestamp": self.timestamp,
            "agents": [
                {
                    "agent": s.agent_name,
                    "signal": s.signal,
                    "score": s.score,
                    "confidence": s.confidence,
                    "reasoning": s.reasoning,
                }
                for s in self.agent_signals
            ],
        }


class BaseAgent(ABC):
    """Base class for all analysis agents."""
    name: str = "base"

    @abstractmethod
    async def analyze(self, symbol: str, **kwargs) -> AgentSignal:
        """Run analysis and return a signal."""
        ...

    def _empty_signal(self, symbol: str, reason: str = "No data") -> AgentSignal:
        return AgentSignal(
            agent_name=self.name,
            symbol=symbol,
            signal="neutral",
            confidence=0.0,
            score=0.0,
            reasoning=reason,
        )
