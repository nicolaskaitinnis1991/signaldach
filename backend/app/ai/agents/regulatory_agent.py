"""RegulatoryAgent — DACH regulation impact assessment."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.ai.agents.base import AgentSignal, BaseAgent
from app.database import get_db

logger = logging.getLogger(__name__)

# Keywords that indicate regulatory risk or opportunity
RISK_KEYWORDS = ["ban", "enforcement", "fine", "penalty", "crackdown", "verbot", "razzia"]
OPPORTUNITY_KEYWORDS = ["approval", "license", "genehmigung", "zulassung", "framework", "clarity"]


class RegulatoryAgent(BaseAgent):
    name = "regulatory"

    async def analyze(self, symbol: str, hours: int = 72, **kwargs) -> AgentSignal:
        with get_db() as conn:
            cur = conn.cursor()
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

            # Get regulation-category items
            cur.execute(
                """SELECT title, summary, sentiment, relevance_score, urgency, published_at
                   FROM items
                   WHERE category = 'regulation'
                   AND published_at > ?
                   ORDER BY relevance_score DESC, published_at DESC
                   LIMIT 30""",
                (cutoff,),
            )
            items = [dict(r) for r in cur.fetchall()]

            # Also check for DACH-specific regulation mentions
            cur.execute(
                """SELECT title, sentiment, relevance_score
                   FROM items
                   WHERE (title LIKE '%BaFin%' OR title LIKE '%FINMA%' OR title LIKE '%MiCA%'
                          OR title LIKE '%FMA%' OR title LIKE '%ESMA%')
                   AND published_at > ?
                   ORDER BY published_at DESC LIMIT 20""",
                (cutoff,),
            )
            dach_items = [dict(r) for r in cur.fetchall()]

        all_items = items + dach_items
        if not all_items:
            return self._empty_signal(symbol, "No regulatory news in timeframe")

        # Analyze risk vs opportunity
        risk_count = 0
        opportunity_count = 0
        for item in all_items:
            title_lower = (item.get("title") or "").lower()
            summary_lower = (item.get("summary") or "").lower()
            text = f"{title_lower} {summary_lower}"

            if any(kw in text for kw in RISK_KEYWORDS):
                risk_count += 1
            if any(kw in text for kw in OPPORTUNITY_KEYWORDS):
                opportunity_count += 1

        # Sentiment from regulatory news
        sentiments = [i.get("sentiment") or 0 for i in all_items if i.get("sentiment") is not None]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0

        # Breaking regulatory news = high impact
        breaking = sum(1 for i in all_items if i.get("urgency") == "breaking")

        # Score
        score = avg_sentiment * 0.5
        score += (opportunity_count - risk_count) / max(len(all_items), 1) * 0.5

        score = max(-1.0, min(1.0, score))
        signal = "bullish" if score > 0.2 else ("bearish" if score < -0.2 else "neutral")

        # Higher confidence with more regulatory news
        confidence = min(1.0, len(all_items) / 15)
        if breaking > 0:
            confidence = min(1.0, confidence + 0.2)

        reasoning_parts = [f"{len(all_items)} regulatory items"]
        if risk_count:
            reasoning_parts.append(f"{risk_count} risk signals")
        if opportunity_count:
            reasoning_parts.append(f"{opportunity_count} opportunity signals")
        if breaking:
            reasoning_parts.append(f"{breaking} breaking regulatory news")
        if dach_items:
            reasoning_parts.append(f"{len(dach_items)} DACH-specific")

        return AgentSignal(
            agent_name=self.name,
            symbol=symbol,
            signal=signal,
            confidence=round(confidence, 3),
            score=round(score, 4),
            reasoning="; ".join(reasoning_parts),
            data={
                "total_items": len(all_items),
                "risk_signals": risk_count,
                "opportunity_signals": opportunity_count,
                "dach_mentions": len(dach_items),
                "breaking_count": breaking,
                "avg_sentiment": round(avg_sentiment, 4),
            },
        )
