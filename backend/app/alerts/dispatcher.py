import json
import logging
import uuid
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)


async def check_and_dispatch_alerts(tenant_id: str, items: list[dict]):
    """Check new items against alert configs and dispatch matching alerts."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM alert_configs WHERE tenant_id = ? AND enabled = 1",
            [tenant_id],
        )
        configs = [dict(row) for row in cur.fetchall()]

    for config in configs:
        conditions = config.get("conditions", {})
        if isinstance(conditions, str):
            conditions = json.loads(conditions)

        channels = config.get("channels", {})
        if isinstance(channels, str):
            channels = json.loads(channels)

        for item in items:
            if _matches(item, conditions):
                await _dispatch(config, item, channels)


def _matches(item: dict, conditions: dict) -> bool:
    """Check if an item matches alert conditions."""
    categories = conditions.get("categories", [])
    if categories and item.get("category") not in categories:
        return False

    min_urgency = conditions.get("min_urgency")
    urgency_order = {"normal": 0, "high": 1, "breaking": 2}
    if min_urgency:
        if urgency_order.get(item.get("urgency", "normal"), 0) < urgency_order.get(min_urgency, 0):
            return False

    min_relevance = conditions.get("min_relevance", 0)
    if item.get("relevance_score", 0) < min_relevance:
        return False

    keywords = conditions.get("keywords", [])
    if keywords:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        if not any(kw.lower() in text for kw in keywords):
            return False

    return True


async def _dispatch(config: dict, item: dict, channels: dict):
    """Send alert via configured channels."""
    if channels.get("webhook"):
        await _send_webhook(channels["webhook"], config, item)

    if channels.get("email") and settings.resend_api_key:
        await _send_email(channels.get("email_address", ""), config, item)

    # Log the alert
    with get_db() as conn:
        cur = conn.cursor()
        alert_id = uuid.uuid4().hex[:12]
        cur.execute(
            """INSERT INTO alert_history (id, alert_config_id, item_id, channel, status, sent_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (alert_id, config["id"], item.get("id", ""), "webhook", "sent",
             datetime.now(timezone.utc).isoformat()),
        )


async def _send_webhook(url: str, config: dict, item: dict):
    """Send alert via webhook (Slack, Discord, custom)."""
    payload = {
        "alert": config.get("name"),
        "item": {
            "title": item.get("title"),
            "summary": item.get("summary"),
            "url": item.get("url"),
            "category": item.get("category"),
            "urgency": item.get("urgency"),
            "relevance_score": item.get("relevance_score"),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json=payload)
        logger.info(f"Webhook sent for: {item.get('title', '')[:50]}")
    except Exception as e:
        logger.error(f"Webhook dispatch failed: {e}")


async def _send_email(to: str, config: dict, item: dict):
    """Send alert via email using Resend."""
    if not to:
        return
    try:
        import resend

        resend.api_key = settings.resend_api_key
        resend.Emails.send(
            {
                "from": "alerts@signaldach.com",
                "to": to,
                "subject": f"[SignalDACH] {item.get('urgency', 'normal').upper()}: {item.get('title', '')[:60]}",
                "html": f"""
                    <h2>{item.get('title')}</h2>
                    <p><strong>Category:</strong> {item.get('category')}</p>
                    <p><strong>Urgency:</strong> {item.get('urgency')}</p>
                    <p><strong>Relevance:</strong> {item.get('relevance_score')}/10</p>
                    <p>{item.get('summary', '')}</p>
                    <a href="{item.get('url', '#')}">Read full article</a>
                """,
            }
        )
        logger.info(f"Email sent to {to} for: {item.get('title', '')[:50]}")
    except Exception as e:
        logger.error(f"Email dispatch failed: {e}")
