"""SentimentAgent — analyzes market sentiment from news and social signals."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.ai.agents.base import AgentSignal, BaseAgent
from app.database import get_db

logger = logging.getLogger(__name__)


class SentimentAgent(BaseAgent):
    name = "sentiment"

    async def analyze(self, symbol: str, hours: int = 24, **kwargs) -> AgentSignal:
        with get_db() as conn:
            cur = conn.cursor()
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

            # Get recent items mentioning this symbol
            symbol_short = symbol.split("/")[0] if "/" in symbol else symbol
            cur.execute(
                """SELECT sentiment, relevance_score, urgency, title
                   FROM items
                   WHERE (title LIKE ? OR title LIKE ?)
                   AND published_at > ?
                   ORDER BY published_at DESC LIMIT 50""",
                (f"%{symbol_short}%", f"%{symbol_short.lower()}%", cutoff),
            )
            rows = [dict(r) for r in cur.fetchall()]

            # Also get fear & greed
            cur.execute(
                """SELECT value FROM market_metrics
                   WHERE metric_type = 'fear_greed_index'
                   ORDER BY ts DESC LIMIT 1"""
            )
            fg_row = cur.fetchone()
            fear_greed = dict(fg_row)["value"] if fg_row else None

        if not rows and fear_greed is None:
            return self._empty_signal(symbol, "No sentiment data available")

        # Aggregate sentiment
        sentiments = [r["sentiment"] for r in rows if r.get("sentiment") is not None]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

        # Weight by relevance
        weighted_sum = sum(
            (r.get("sentiment") or 0) * (r.get("relevance_score") or 5)
            for r in rows if r.get("sentiment") is not None
        )
        weight_total = sum(
            r.get("relevance_score") or 5
            for r in rows if r.get("sentiment") is not None
        )
        weighted_sentiment = weighted_sum / weight_total if weight_total > 0 else 0.0

        # Count urgency signals
        breaking_count = sum(1 for r in rows if r.get("urgency") == "breaking")
        high_count = sum(1 for r in rows if r.get("urgency") == "high")

        # Determine signal
        score = weighted_sentiment
        if fear_greed is not None:
            fg_normalized = (fear_greed - 50) / 50  # -1 to 1
            score = score * 0.7 + fg_normalized * 0.3

        if score > 0.3:
            signal = "bullish"
        elif score < -0.3:
            signal = "bearish"
        else:
            signal = "neutral"

        confidence = min(1.0, len(sentiments) / 20)  # More data = more confident

        reasoning_parts = [f"{len(rows)} news items analyzed"]
        if sentiments:
            reasoning_parts.append(f"avg sentiment: {avg_sentiment:.2f}")
        if fear_greed is not None:
            reasoning_parts.append(f"Fear & Greed: {fear_greed:.0f}/100")
        if breaking_count:
            reasoning_parts.append(f"{breaking_count} breaking news")

        return AgentSignal(
            agent_name=self.name,
            symbol=symbol,
            signal=signal,
            confidence=round(confidence, 3),
            score=round(score, 4),
            reasoning="; ".join(reasoning_parts),
            data={
                "articles_count": len(rows),
                "avg_sentiment": round(avg_sentiment, 4),
                "weighted_sentiment": round(weighted_sentiment, 4),
                "fear_greed": fear_greed,
                "breaking_news": breaking_count,
                "high_urgency": high_count,
            },
        )
