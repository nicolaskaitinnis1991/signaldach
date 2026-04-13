"""AI-powered Daily Intelligence Report Generator.

Generates executive briefings from the last 24h of scraped data.
Uses Anthropic Claude or OpenAI GPT when available, falls back to rule-based.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

REPORT_SYSTEM_PROMPT = """You are a senior intelligence analyst at a crypto investment fund operating in the DACH region (Germany, Austria, Switzerland). Your audience is fund managers and institutional investors.

Generate a concise Daily Intelligence Report based on the data provided. Structure your report EXACTLY as this JSON:

{
  "executive_summary": "2-3 sentences: What happened in the last 24h that matters for a DACH crypto fund?",
  "market_risk_score": <integer 1-100, where 1=very safe, 100=extreme risk>,
  "market_risk_label": "<one of: LOW, MODERATE, ELEVATED, HIGH, EXTREME>",
  "sentiment_assessment": "1-2 sentences on market sentiment direction and strength",
  "regulatory_risk_de": {
    "score": <1-100>,
    "summary": "1-2 sentences about German regulatory landscape"
  },
  "regulatory_risk_ch": {
    "score": <1-100>,
    "summary": "1-2 sentences about Swiss regulatory landscape"
  },
  "key_events": [
    {"title": "...", "impact": "HIGH/MEDIUM/LOW", "description": "1 sentence why this matters"},
    ...max 5 events
  ],
  "action_items": [
    "Specific action the fund should consider taking",
    ...max 3 items
  ],
  "market_outlook": "2-3 sentences: short-term outlook based on current signals",
  "dach_specific": "1-2 sentences about anything specifically relevant to DACH operations"
}

Be direct, factual, and actionable. No marketing language. Think like a Bloomberg analyst."""


def _get_report_data(hours: int = 24) -> dict:
    """Gather all data needed for the report from the last N hours."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    with get_db() as conn:
        cur = conn.cursor()

        # Total items in period
        cur.execute("SELECT COUNT(*) as cnt FROM items WHERE created_at >= ?", [cutoff])
        total = cur.fetchone()["cnt"]

        # By category
        cur.execute(
            "SELECT category, COUNT(*) as cnt FROM items WHERE created_at >= ? GROUP BY category",
            [cutoff],
        )
        by_category = {row["category"]: row["cnt"] for row in cur.fetchall()}

        # By urgency
        cur.execute(
            "SELECT urgency, COUNT(*) as cnt FROM items WHERE created_at >= ? GROUP BY urgency",
            [cutoff],
        )
        by_urgency = {row["urgency"]: row["cnt"] for row in cur.fetchall()}

        # Average sentiment
        cur.execute(
            "SELECT AVG(sentiment) as avg_sent FROM items WHERE created_at >= ? AND sentiment IS NOT NULL",
            [cutoff],
        )
        row = cur.fetchone()
        avg_sentiment = round(float(row["avg_sent"]), 3) if row and row["avg_sent"] else 0.0

        # Previous period sentiment for comparison
        prev_cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours * 2)).isoformat()
        cur.execute(
            "SELECT AVG(sentiment) as avg_sent FROM items WHERE created_at >= ? AND created_at < ? AND sentiment IS NOT NULL",
            [prev_cutoff, cutoff],
        )
        row = cur.fetchone()
        prev_sentiment = round(float(row["avg_sent"]), 3) if row and row["avg_sent"] else 0.0

        # Top breaking/high items
        cur.execute(
            """SELECT title, category, relevance_score, urgency, sentiment, url, source_id, ai_metadata
               FROM items WHERE created_at >= ? AND urgency IN ('breaking', 'high')
               ORDER BY relevance_score DESC LIMIT 10""",
            [cutoff],
        )
        high_priority = []
        for r in cur.fetchall():
            item = dict(r)
            if isinstance(item.get("ai_metadata"), str):
                try:
                    item["ai_metadata"] = json.loads(item["ai_metadata"])
                except (json.JSONDecodeError, TypeError):
                    item["ai_metadata"] = {}
            high_priority.append(item)

        # Top regulation items
        cur.execute(
            """SELECT title, relevance_score, sentiment, url, ai_metadata
               FROM items WHERE created_at >= ? AND category = 'regulation'
               ORDER BY relevance_score DESC LIMIT 10""",
            [cutoff],
        )
        regulation_items = []
        for r in cur.fetchall():
            item = dict(r)
            if isinstance(item.get("ai_metadata"), str):
                try:
                    item["ai_metadata"] = json.loads(item["ai_metadata"])
                except (json.JSONDecodeError, TypeError):
                    item["ai_metadata"] = {}
            regulation_items.append(item)

        # Top keywords (from keyword_trends)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cur.execute(
            """SELECT keyword, count, is_spike FROM keyword_trends
               WHERE date = ? ORDER BY count DESC LIMIT 15""",
            [today],
        )
        trending = [dict(r) for r in cur.fetchall()]

        # Active spikes
        cur.execute(
            """SELECT keyword, count, avg_count_7d FROM keyword_trends
               WHERE is_spike = 1 AND date >= date('now', '-1 day')
               ORDER BY count DESC LIMIT 5""",
        )
        spikes = [dict(r) for r in cur.fetchall()]

    return {
        "period_hours": hours,
        "total_items": total,
        "by_category": by_category,
        "by_urgency": by_urgency,
        "avg_sentiment": avg_sentiment,
        "prev_sentiment": prev_sentiment,
        "sentiment_direction": "improving" if avg_sentiment > prev_sentiment else "declining" if avg_sentiment < prev_sentiment else "stable",
        "high_priority_items": high_priority,
        "regulation_items": regulation_items,
        "trending_keywords": trending,
        "keyword_spikes": spikes,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def generate_report(hours: int = 24) -> dict:
    """Generate the intelligence report. Uses LLM if available, otherwise rule-based."""
    data = _get_report_data(hours)

    # Try LLM-powered report
    report = await _try_llm_report(data)
    if report:
        report["_meta"] = {
            "generated_at": data["generated_at"],
            "period_hours": hours,
            "total_signals": data["total_items"],
            "model": report.get("_model", "unknown"),
            "type": "ai",
        }
        report.pop("_model", None)
        return report

    # Fallback: rule-based report
    return _rule_based_report(data)


async def _try_llm_report(data: dict) -> Optional[dict]:
    """Try generating report with Anthropic Claude or OpenAI."""

    # Build the data summary for the LLM
    user_prompt = f"""Here is the intelligence data from the last {data['period_hours']} hours:

SUMMARY:
- Total signals collected: {data['total_items']}
- By category: {json.dumps(data['by_category'])}
- By urgency: {json.dumps(data['by_urgency'])}
- Average sentiment: {data['avg_sentiment']} (previous period: {data['prev_sentiment']}, direction: {data['sentiment_direction']})

HIGH PRIORITY EVENTS:
{_format_items_for_llm(data['high_priority_items'])}

REGULATORY EVENTS:
{_format_items_for_llm(data['regulation_items'])}

TRENDING KEYWORDS: {json.dumps(data['trending_keywords'][:10])}
KEYWORD SPIKES: {json.dumps(data['keyword_spikes'])}

Generate the Daily Intelligence Report as JSON."""

    # Try Anthropic first
    if settings.anthropic_api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            response = client.messages.create(
                model=settings.llm_model_anthropic,
                max_tokens=1500,
                system=REPORT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.3,
            )
            text = response.content[0].text
            # Extract JSON from response
            report = _extract_json(text)
            if report:
                report["_model"] = f"claude:{settings.llm_model_anthropic}"
                return report
        except Exception as e:
            logger.warning(f"Anthropic report generation failed: {e}")

    # Try OpenAI
    if settings.openai_api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.llm_model_openai,
                messages=[
                    {"role": "system", "content": REPORT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            text = response.choices[0].message.content
            report = _extract_json(text)
            if report:
                report["_model"] = f"openai:{settings.llm_model_openai}"
                return report
        except Exception as e:
            logger.warning(f"OpenAI report generation failed: {e}")

    return None


def _format_items_for_llm(items: list[dict]) -> str:
    """Format items list for LLM consumption."""
    if not items:
        return "None"
    lines = []
    for item in items[:10]:
        keywords = item.get("ai_metadata", {}).get("keywords", [])
        entities = item.get("ai_metadata", {}).get("entities", {})
        lines.append(
            f"- [{item.get('urgency', 'normal').upper()}] (relevance: {item.get('relevance_score', 0)}/10, "
            f"sentiment: {item.get('sentiment', 'N/A')}) {item.get('title', 'Untitled')}"
            f"\n  Keywords: {', '.join(keywords) if keywords else 'none'}"
            f"\n  Entities: {json.dumps(entities) if entities else 'none'}"
        )
    return "\n".join(lines)


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from LLM response text."""
    # Try direct parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try to find JSON block in text
    import re
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except (json.JSONDecodeError, TypeError):
            pass

    return None


def _rule_based_report(data: dict) -> dict:
    """Generate a rule-based report when no LLM is available."""
    total = data["total_items"]
    cats = data["by_category"]
    urgencies = data["by_urgency"]
    sentiment = data["avg_sentiment"]
    prev_sentiment = data["prev_sentiment"]
    direction = data["sentiment_direction"]

    # Market risk score
    breaking_count = urgencies.get("breaking", 0)
    high_count = urgencies.get("high", 0)
    risk_base = 30
    risk_base += breaking_count * 15
    risk_base += high_count * 3
    if sentiment < -0.3:
        risk_base += 20
    elif sentiment < -0.1:
        risk_base += 10
    risk_score = min(100, max(1, risk_base))

    risk_label = (
        "EXTREME" if risk_score >= 80 else
        "HIGH" if risk_score >= 60 else
        "ELEVATED" if risk_score >= 40 else
        "MODERATE" if risk_score >= 20 else
        "LOW"
    )

    # Regulatory assessment
    reg_count = cats.get("regulation", 0)
    reg_items = data["regulation_items"]
    reg_de_items = [i for i in reg_items if any(kw in i.get("title", "").lower() for kw in ["bafin", "germany", "deutsch", "german"])]
    reg_ch_items = [i for i in reg_items if any(kw in i.get("title", "").lower() for kw in ["finma", "swiss", "schweiz", "switzerland"])]

    de_risk = min(100, 20 + len(reg_de_items) * 10 + breaking_count * 15)
    ch_risk = min(100, 20 + len(reg_ch_items) * 10 + breaking_count * 15)

    # Key events
    key_events = []
    for item in data["high_priority_items"][:5]:
        impact = "HIGH" if item.get("urgency") == "breaking" else "MEDIUM" if item.get("relevance_score", 0) >= 7 else "LOW"
        key_events.append({
            "title": item.get("title", "")[:120],
            "impact": impact,
            "description": f"Relevance {item.get('relevance_score', 0)}/10, Sentiment: {'positive' if (item.get('sentiment') or 0) > 0 else 'negative' if (item.get('sentiment') or 0) < 0 else 'neutral'}",
        })

    # Action items
    actions = []
    if breaking_count > 0:
        actions.append(f"Review {breaking_count} breaking alert(s) immediately — potential impact on fund operations")
    if reg_count > 5:
        actions.append(f"High regulatory activity ({reg_count} events) — schedule compliance review")
    if sentiment < -0.2:
        actions.append("Market sentiment significantly negative — consider risk exposure review")
    if direction == "declining":
        actions.append("Sentiment trending downward vs previous period — monitor for trend continuation")
    if len(data["keyword_spikes"]) > 0:
        spike_kws = [s["keyword"] for s in data["keyword_spikes"][:3]]
        actions.append(f"Keyword spikes detected: {', '.join(spike_kws)} — investigate potential market-moving events")
    if not actions:
        actions.append("No immediate actions required — continue monitoring")

    # Sentiment assessment
    sent_str = f"Market sentiment is {direction} at {sentiment:.3f}"
    if prev_sentiment != 0:
        change = sentiment - prev_sentiment
        sent_str += f" (change: {'+' if change > 0 else ''}{change:.3f} vs previous period)"

    # Executive summary
    summary_parts = [f"{total} signals collected in the last {data['period_hours']}h."]
    if breaking_count > 0:
        summary_parts.append(f"{breaking_count} breaking alerts require attention.")
    summary_parts.append(f"Market sentiment is {direction} ({sentiment:.2f}).")
    if reg_count > 0:
        summary_parts.append(f"{reg_count} regulatory events tracked across DACH.")

    return {
        "executive_summary": " ".join(summary_parts),
        "market_risk_score": risk_score,
        "market_risk_label": risk_label,
        "sentiment_assessment": sent_str,
        "regulatory_risk_de": {
            "score": de_risk,
            "summary": f"{len(reg_de_items)} BaFin/German regulatory events detected" if reg_de_items else "No significant German regulatory activity",
        },
        "regulatory_risk_ch": {
            "score": ch_risk,
            "summary": f"{len(reg_ch_items)} FINMA/Swiss regulatory events detected" if reg_ch_items else "No significant Swiss regulatory activity",
        },
        "key_events": key_events,
        "action_items": actions[:3],
        "market_outlook": f"Based on {total} signals with average sentiment {sentiment:.2f} ({direction}), the short-term outlook is {'cautious' if sentiment < -0.1 else 'neutral' if abs(sentiment) <= 0.1 else 'moderately positive'}. Monitor breaking events closely.",
        "dach_specific": f"Regulatory activity: {len(reg_de_items)} DE events, {len(reg_ch_items)} CH events. {'Elevated regulatory scrutiny in the region.' if reg_count > 10 else 'Normal regulatory activity levels.'}",
        "_meta": {
            "generated_at": data["generated_at"],
            "period_hours": data["period_hours"],
            "total_signals": total,
            "model": "rule-based",
            "type": "rule-based",
        },
    }
