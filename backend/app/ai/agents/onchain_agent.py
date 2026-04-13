"""OnChainAgent — DeFi TVL, stablecoin flows, whale activity analysis."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.ai.agents.base import AgentSignal, BaseAgent
from app.database import get_db

logger = logging.getLogger(__name__)


class OnChainAgent(BaseAgent):
    name = "onchain"

    async def analyze(self, symbol: str, **kwargs) -> AgentSignal:
        with get_db() as conn:
            cur = conn.cursor()
            cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            cutoff_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

            # Total DeFi TVL trend
            cur.execute(
                """SELECT value, ts FROM onchain_metrics
                   WHERE metric_type = 'chain_tvl'
                   AND ts > ?
                   ORDER BY ts ASC""",
                (cutoff_7d,),
            )
            tvl_rows = [dict(r) for r in cur.fetchall()]

            # Stablecoin market cap
            cur.execute(
                """SELECT value FROM market_metrics
                   WHERE metric_type = 'stablecoin_total_mcap'
                   ORDER BY ts DESC LIMIT 2"""
            )
            stable_rows = [dict(r) for r in cur.fetchall()]

            # Top yield anomalies (unusually high yields = risk)
            cur.execute(
                """SELECT value, protocol, chain FROM onchain_metrics
                   WHERE metric_type = 'defi_yield'
                   AND ts > ?
                   ORDER BY value DESC LIMIT 5""",
                (cutoff_24h,),
            )
            yield_rows = [dict(r) for r in cur.fetchall()]

        signals = []
        score = 0.0
        data = {}

        # TVL trend analysis
        if len(tvl_rows) >= 2:
            tvl_values = [r["value"] for r in tvl_rows]
            first_tvl = sum(tvl_values[:len(tvl_values)//4]) / max(1, len(tvl_values)//4)
            last_tvl = sum(tvl_values[-len(tvl_values)//4:]) / max(1, len(tvl_values)//4)
            tvl_change = (last_tvl - first_tvl) / first_tvl if first_tvl > 0 else 0

            data["tvl_change_pct"] = round(tvl_change * 100, 2)
            if tvl_change > 0.05:
                signals.append("TVL growing (bullish DeFi activity)")
                score += 0.3
            elif tvl_change < -0.05:
                signals.append("TVL declining (capital outflow)")
                score -= 0.3

        # Stablecoin inflow/outflow
        if len(stable_rows) >= 2:
            stable_change = (stable_rows[0]["value"] - stable_rows[1]["value"]) / stable_rows[1]["value"]
            data["stablecoin_change_pct"] = round(stable_change * 100, 2)
            if stable_change > 0.01:
                signals.append("Stablecoin mcap growing (dry powder entering)")
                score += 0.2
            elif stable_change < -0.01:
                signals.append("Stablecoin outflow (risk-off)")
                score -= 0.2

        # Extreme yields = risk signal
        if yield_rows:
            max_yield = yield_rows[0]["value"]
            data["max_yield_apy"] = round(max_yield, 1)
            if max_yield > 100:
                signals.append(f"Extreme yield detected ({max_yield:.0f}% APY) — potential risk")
                score -= 0.1

        if not signals:
            return self._empty_signal(symbol, "No on-chain data available")

        score = max(-1.0, min(1.0, score))
        signal = "bullish" if score > 0.2 else ("bearish" if score < -0.2 else "neutral")
        confidence = min(1.0, len(tvl_rows) / 30)

        return AgentSignal(
            agent_name=self.name,
            symbol=symbol,
            signal=signal,
            confidence=round(confidence, 3),
            score=round(score, 4),
            reasoning="; ".join(signals),
            data=data,
        )
