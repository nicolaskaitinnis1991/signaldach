"""TechnicalAgent — price pattern analysis, momentum, trend detection."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

from app.ai.agents.base import AgentSignal, BaseAgent
from app.database import get_db

logger = logging.getLogger(__name__)


class TechnicalAgent(BaseAgent):
    name = "technical"

    async def analyze(self, symbol: str, **kwargs) -> AgentSignal:
        with get_db() as conn:
            cur = conn.cursor()

            # Get price history (last 7 days)
            cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            cur.execute(
                """SELECT price, volume_24h, change_pct_24h, ts
                   FROM price_ticks
                   WHERE symbol LIKE ?
                   AND ts > ?
                   ORDER BY ts ASC""",
                (f"%{symbol.split('/')[0]}%", cutoff),
            )
            rows = [dict(r) for r in cur.fetchall()]

        if len(rows) < 5:
            return self._empty_signal(symbol, f"Insufficient price data ({len(rows)} points)")

        prices = [r["price"] for r in rows]
        latest = prices[-1]
        volumes = [r.get("volume_24h") for r in rows if r.get("volume_24h")]

        # --- Momentum indicators ---
        # Short-term momentum (last 20% of data vs previous)
        split = max(1, len(prices) // 5)
        recent_avg = sum(prices[-split:]) / split
        older_avg = sum(prices[:split]) / split if split > 0 else latest
        momentum = (recent_avg - older_avg) / older_avg if older_avg > 0 else 0

        # Simple Moving Averages
        sma_short = sum(prices[-min(10, len(prices)):]) / min(10, len(prices))
        sma_long = sum(prices) / len(prices)
        sma_crossover = sma_short > sma_long  # Golden cross signal

        # Volatility (standard deviation of returns)
        returns = []
        for i in range(1, len(prices)):
            if prices[i - 1] > 0:
                returns.append((prices[i] - prices[i - 1]) / prices[i - 1])

        volatility = 0.0
        if returns:
            mean_ret = sum(returns) / len(returns)
            variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
            volatility = math.sqrt(variance)

        # RSI-like indicator (simplified)
        gains = [r for r in returns if r > 0]
        losses = [-r for r in returns if r < 0]
        avg_gain = sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses) / len(losses) if losses else 0.001
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi = 100 - (100 / (1 + rs))

        # Volume trend
        vol_trend = 0.0
        if len(volumes) >= 4:
            recent_vol = sum(volumes[-len(volumes)//4:]) / (len(volumes)//4)
            older_vol = sum(volumes[:len(volumes)//4]) / (len(volumes)//4)
            vol_trend = (recent_vol - older_vol) / older_vol if older_vol > 0 else 0

        # --- Compute score ---
        score = 0.0
        score += momentum * 2  # Momentum signal
        score += (0.2 if sma_crossover else -0.2)  # SMA crossover
        score += (rsi - 50) / 100  # RSI contribution

        # Clamp to [-1, 1]
        score = max(-1.0, min(1.0, score))

        if score > 0.3:
            signal = "bullish"
        elif score < -0.3:
            signal = "bearish"
        else:
            signal = "neutral"

        # Confidence based on data density and volatility
        confidence = min(1.0, len(rows) / 50) * (1 - min(volatility * 5, 0.5))

        reasoning_parts = []
        reasoning_parts.append(f"Price ${latest:,.2f}")
        reasoning_parts.append(f"Momentum: {momentum*100:+.1f}%")
        reasoning_parts.append(f"RSI: {rsi:.0f}")
        reasoning_parts.append(f"SMA {'golden' if sma_crossover else 'death'} cross")
        reasoning_parts.append(f"Volatility: {volatility*100:.2f}%")

        return AgentSignal(
            agent_name=self.name,
            symbol=symbol,
            signal=signal,
            confidence=round(max(0, confidence), 3),
            score=round(score, 4),
            reasoning="; ".join(reasoning_parts),
            data={
                "latest_price": latest,
                "momentum": round(momentum, 4),
                "rsi": round(rsi, 1),
                "sma_crossover": sma_crossover,
                "volatility": round(volatility, 4),
                "volume_trend": round(vol_trend, 4),
                "data_points": len(rows),
            },
        )
