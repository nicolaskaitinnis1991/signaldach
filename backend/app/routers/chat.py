"""Conversational Intelligence API.

Natural language interface to the entire SignalDACH intelligence engine.
Users can ask questions like:
- "What's happening with BTC?"
- "Should I be worried about MiCA?"
- "Show me unusual activity"
- "What's the market regime right now?"

Routes queries to the appropriate backend modules.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"], dependencies=[Depends(get_current_user)])


class ChatMessage(BaseModel):
    message: str
    context: dict = {}  # Optional context (e.g., portfolio, preferences)


class ChatResponse(BaseModel):
    reply: str
    data: dict = {}
    sources: list[str] = []
    suggested_actions: list[str] = []


# Intent detection patterns
_INTENTS = [
    ("signal", re.compile(r"signal|analyze|analysis|what.*think|should i|buy|sell", re.I)),
    ("price", re.compile(r"price|how much|what.*worth|current.*price", re.I)),
    ("regime", re.compile(r"regime|market.*state|risk.on|risk.off|phase", re.I)),
    ("anomaly", re.compile(r"unusual|anomal|strange|weird|spike|outlier", re.I)),
    ("regulation", re.compile(r"regulat|mica|bafin|finma|compliance|legal", re.I)),
    ("fear_greed", re.compile(r"fear|greed|sentiment|mood|feeling", re.I)),
    ("tvl", re.compile(r"tvl|defi|liquidity|locked|protocol", re.I)),
    ("funding", re.compile(r"funding|leverage|futures|perpetual|open interest", re.I)),
    ("entity", re.compile(r"who.*connected|relationship|network|linked|graph", re.I)),
    ("summary", re.compile(r"summary|overview|what.*happening|update|brief", re.I)),
]


def _detect_intent(message: str) -> str:
    """Detect the user's intent from their message."""
    for intent, pattern in _INTENTS:
        if pattern.search(message):
            return intent
    return "summary"


def _extract_symbol(message: str) -> str:
    """Extract a crypto symbol from the message."""
    symbols = {
        "btc": "BTC/USDT", "bitcoin": "BTC/USDT",
        "eth": "ETH/USDT", "ethereum": "ETH/USDT",
        "sol": "SOL/USDT", "solana": "SOL/USDT",
        "xrp": "XRP/USDT", "ripple": "XRP/USDT",
        "bnb": "BNB/USDT",
        "ada": "ADA/USDT", "cardano": "ADA/USDT",
        "doge": "DOGE/USDT", "dogecoin": "DOGE/USDT",
        "avax": "AVAX/USDT", "avalanche": "AVAX/USDT",
    }
    msg_lower = message.lower()
    for key, sym in symbols.items():
        if key in msg_lower:
            return sym
    return "BTC/USDT"


@router.post("/", response_model=ChatResponse)
async def chat(msg: ChatMessage):
    """Process a natural language query about the crypto market."""
    intent = _detect_intent(msg.message)
    symbol = _extract_symbol(msg.message)

    try:
        if intent == "signal":
            return await _handle_signal(symbol)
        elif intent == "price":
            return await _handle_price(symbol)
        elif intent == "regime":
            return await _handle_regime()
        elif intent == "anomaly":
            return await _handle_anomaly()
        elif intent == "regulation":
            return await _handle_regulation()
        elif intent == "fear_greed":
            return await _handle_fear_greed()
        elif intent == "tvl":
            return await _handle_tvl()
        elif intent == "funding":
            return await _handle_funding(symbol)
        elif intent == "entity":
            return await _handle_entity(msg.message)
        else:
            return await _handle_summary(symbol)
    except Exception as e:
        logger.error("Chat handler error: %s", e)
        return ChatResponse(
            reply=f"Entschuldigung, bei der Analyse ist ein Fehler aufgetreten. Bitte versuche es erneut.",
            data={"error": str(e)},
        )


async def _handle_signal(symbol: str) -> ChatResponse:
    from app.ai.agents.synthesis import get_market_signal
    data = await get_market_signal(symbol)

    signal = data["overall_signal"]
    score = data["overall_score"]
    conf = data["confidence"]

    signal_emoji_map = {
        "strong_buy": "Strong Buy", "buy": "Buy", "neutral": "Neutral",
        "sell": "Sell", "strong_sell": "Strong Sell",
    }

    reply = (
        f"**{symbol} Signal: {signal_emoji_map.get(signal, signal)}** "
        f"(Score: {score:+.2f}, Confidence: {conf:.0%})\n\n"
    )
    for agent in data.get("agents", []):
        reply += f"- **{agent['agent'].title()}**: {agent['signal']} ({agent['score']:+.2f}) — {agent['reasoning']}\n"

    if data.get("risk_factors"):
        reply += f"\n**Risks:** {'; '.join(data['risk_factors'][:3])}"

    return ChatResponse(
        reply=reply,
        data=data,
        sources=["multi-agent-engine"],
        suggested_actions=["Check anomalies", "View price history", "Run scenario simulation"],
    )


async def _handle_price(symbol: str) -> ChatResponse:
    from app.database import get_db
    with get_db() as conn:
        cur = conn.cursor()
        short = symbol.split("/")[0]
        cur.execute(
            "SELECT price, change_pct_24h, exchange, ts FROM price_ticks "
            "WHERE symbol LIKE ? ORDER BY ts DESC LIMIT 1",
            (f"%{short}%",),
        )
        row = cur.fetchone()

    if not row:
        return ChatResponse(reply=f"Keine Preisdaten für {symbol} verfügbar.")

    d = dict(row)
    change = d.get("change_pct_24h") or 0
    direction = "up" if change > 0 else "down" if change < 0 else "flat"

    return ChatResponse(
        reply=f"**{symbol}**: ${d['price']:,.2f} ({change:+.1f}% 24h, {direction})\nSource: {d['exchange']} | {d['ts']}",
        data=d,
        sources=[d.get("exchange", "")],
    )


async def _handle_regime() -> ChatResponse:
    from app.ai.causal import detect_regime
    data = detect_regime()

    return ChatResponse(
        reply=(
            f"**Market Regime: {data['regime'].replace('_', ' ').title()}** "
            f"(Confidence: {data['confidence']:.0%})\n\n"
            f"{'  '.join(data.get('reasons', []))}"
        ),
        data=data,
        sources=["causal-intelligence"],
        suggested_actions=["View signal analysis", "Check anomalies"],
    )


async def _handle_anomaly() -> ChatResponse:
    from app.ai.anomaly import run_full_anomaly_scan
    data = run_full_anomaly_scan()
    total = data.get("total_anomalies", 0)

    if total == 0:
        reply = "Keine Anomalien erkannt. Alle Metriken im normalen Bereich."
    else:
        reply = f"**{total} Anomalien erkannt:**\n\n"
        for key, result in data.items():
            if isinstance(result, dict) and result.get("anomaly_count", 0) > 0:
                reply += f"- **{key}**: {result['anomaly_count']} Anomalien\n"

    return ChatResponse(reply=reply, data=data, sources=["anomaly-detection"])


async def _handle_fear_greed() -> ChatResponse:
    from app.database import get_db
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT value, metadata_json, ts FROM market_metrics "
            "WHERE metric_type = 'fear_greed_index' ORDER BY ts DESC LIMIT 1"
        )
        row = cur.fetchone()

    if not row:
        return ChatResponse(reply="Keine Fear & Greed Daten verfügbar.")

    d = dict(row)
    value = d["value"]
    meta = json.loads(d.get("metadata_json") or "{}") if d.get("metadata_json") else {}
    classification = meta.get("classification", "")

    return ChatResponse(
        reply=f"**Fear & Greed Index: {value:.0f}/100 ({classification})**\n\nStand: {d['ts']}",
        data=d,
        sources=["alternative.me"],
    )


async def _handle_regulation() -> ChatResponse:
    from app.database import get_db
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT title, summary, urgency, published_at FROM items "
            "WHERE category = 'regulation' ORDER BY published_at DESC LIMIT 5"
        )
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return ChatResponse(reply="Keine aktuellen Regulierungs-News gefunden.")

    reply = f"**{len(rows)} aktuelle Regulierungs-News:**\n\n"
    for r in rows:
        urgency_marker = " [BREAKING]" if r.get("urgency") == "breaking" else ""
        reply += f"- {r['title']}{urgency_marker}\n"

    return ChatResponse(
        reply=reply,
        data={"items": rows},
        sources=["news-pipeline"],
    )


async def _handle_tvl() -> ChatResponse:
    from app.database import get_db
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT protocol, value, chain FROM onchain_metrics "
            "WHERE metric_type = 'tvl' ORDER BY ts DESC LIMIT 10"
        )
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return ChatResponse(reply="Keine TVL-Daten verfügbar.")

    reply = "**Top DeFi Protocols by TVL:**\n\n"
    for r in rows[:10]:
        val = r["value"]
        fmt = f"${val/1e9:.1f}B" if val >= 1e9 else f"${val/1e6:.0f}M"
        reply += f"- **{r['protocol']}** ({r.get('chain', '?')}): {fmt}\n"

    return ChatResponse(reply=reply, data={"protocols": rows}, sources=["defillama"])


async def _handle_funding(symbol: str) -> ChatResponse:
    from app.database import get_db
    with get_db() as conn:
        cur = conn.cursor()
        short = symbol.split("/")[0]
        cur.execute(
            "SELECT value, symbol, metadata_json, ts FROM market_metrics "
            "WHERE metric_type = 'funding_rate' AND symbol LIKE ? "
            "ORDER BY ts DESC LIMIT 1",
            (f"%{short}%",),
        )
        row = cur.fetchone()

    if not row:
        return ChatResponse(reply=f"Keine Funding Rate Daten für {symbol}.")

    d = dict(row)
    rate = d["value"]
    direction = "Long zahlt Short" if rate > 0 else "Short zahlt Long"

    return ChatResponse(
        reply=f"**{symbol} Funding Rate: {rate:.4%}** ({direction})\nStand: {d['ts']}",
        data=d,
        sources=["binance-futures"],
    )


async def _handle_entity(message: str) -> ChatResponse:
    from app.ai.knowledge_graph import get_entity_connections
    # Try to extract entity from message
    words = message.split()
    entity = "BTC"
    for w in words:
        if w.upper() in ("BTC", "ETH", "SOL", "XRP", "BINANCE", "BAFIN", "FINMA", "MICA"):
            entity = w.upper()
            break

    connections = get_entity_connections(entity, limit=10)
    if not connections:
        return ChatResponse(reply=f"Keine Verbindungen für {entity} im Knowledge Graph.")

    reply = f"**Entity Network: {entity}** ({len(connections)} Verbindungen)\n\n"
    for c in connections[:10]:
        reply += f"- {c['entity']} ({c['entity_type']}) — weight: {c['weight']:.0f}\n"

    return ChatResponse(reply=reply, data={"connections": connections}, sources=["knowledge-graph"])


async def _handle_summary(symbol: str) -> ChatResponse:
    """General market summary."""
    from app.ai.agents.synthesis import get_market_signal
    from app.ai.causal import detect_regime

    signal_data = await get_market_signal(symbol)
    regime_data = detect_regime(days=7)

    signal = signal_data["overall_signal"]
    score = signal_data["overall_score"]
    regime = regime_data["regime"].replace("_", " ").title()

    reply = (
        f"**Market Update ({symbol})**\n\n"
        f"Signal: **{signal.replace('_', ' ').title()}** ({score:+.2f})\n"
        f"Regime: **{regime}**\n\n"
        f"**Agent Breakdown:**\n"
    )
    for agent in signal_data.get("agents", []):
        reply += f"- {agent['agent'].title()}: {agent['signal']} ({agent['score']:+.2f})\n"

    return ChatResponse(
        reply=reply,
        data={"signal": signal_data, "regime": regime_data},
        sources=["multi-agent-engine", "causal-intelligence"],
        suggested_actions=["Deep dive into anomalies", "Check regulatory news", "Run scenario simulation"],
    )
