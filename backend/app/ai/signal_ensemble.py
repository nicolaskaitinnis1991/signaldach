"""Signal Ensemble -- combines multiple agent signals with adaptive weights.

Instead of fixed agent weights, uses historical accuracy to weight agents.
Periodically recalculates weights based on scorecard performance.

Ensemble methods:
1. Weighted Average (current approach, but with adaptive weights)
2. Confidence-Weighted Voting

Calibration algorithm:
    1. For each agent, look at signal_scores where signal_type matches agent name
    2. Compare signal direction with actual price movement over eval_hours
    3. Calculate accuracy = correct_predictions / total_predictions
    4. New weight = (accuracy * 2) -- normalize so all weights sum to 1.0
    5. Apply exponential smoothing: final = 0.7 * new + 0.3 * old
    6. Minimum weight: 0.05 (no agent gets fully silenced)
"""

from __future__ import annotations

import logging
import math
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.ai.agents.base import AgentSignal

logger = logging.getLogger(__name__)

# Default weights (used before enough history exists)
DEFAULT_WEIGHTS: dict[str, float] = {
    "sentiment": 0.25,
    "technical": 0.30,
    "onchain": 0.20,
    "regulatory": 0.15,
    "anomaly": 0.10,
}

# Minimum weight any agent can have (prevents full silencing)
MIN_WEIGHT = 0.05

# Minimum number of scored signals before we trust calibration
MIN_SAMPLE_COUNT = 10

# Exponential smoothing factor (higher = more weight on new data)
SMOOTHING_ALPHA = 0.7


def _ensure_ensemble_table() -> None:
    """Create ensemble_weights table if it does not exist."""
    try:
        from app.database import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ensemble_weights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name TEXT NOT NULL,
                    weight REAL NOT NULL,
                    accuracy REAL,
                    sample_count INTEGER,
                    calibrated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(agent_name, calibrated_at)
                )
            """)
    except Exception as e:
        logger.debug("Could not ensure ensemble_weights table: %s", e)


@dataclass
class EnsembleResult:
    """Result from combining agent signals."""
    score: float  # -1 to 1
    confidence: float  # 0 to 1
    method: str
    weights_used: dict[str, float]
    individual_contributions: dict[str, float]
    signal: str  # "strong_buy", "buy", "neutral", "sell", "strong_sell"


class SignalEnsemble:
    """Adaptive signal ensemble that learns from historical accuracy."""

    def __init__(self) -> None:
        self._weights: dict[str, float] = dict(DEFAULT_WEIGHTS)
        self._last_calibration: Optional[datetime] = None
        self._lock = threading.Lock()
        # Create table on init (safe to call multiple times)
        _ensure_ensemble_table()

    def get_weights(self) -> dict[str, float]:
        """Get current agent weights (thread-safe copy)."""
        with self._lock:
            return dict(self._weights)

    @staticmethod
    def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
        """Normalize weights to sum to 1.0, enforcing MIN_WEIGHT floor.

        Algorithm: lock low agents at MIN_WEIGHT, distribute remaining
        budget (1.0 - locked_total) proportionally among unlocked agents.
        """
        if not weights:
            return dict(DEFAULT_WEIGHTS)

        n = len(weights)
        result = {k: max(v, 0.0) for k, v in weights.items()}
        total = sum(result.values())
        if total <= 0:
            return {k: 1.0 / n for k in result}

        # Normalize to 1.0 first
        result = {k: v / total for k, v in result.items()}

        # Iteratively lock agents at MIN_WEIGHT and redistribute
        locked: set = set()
        for _ in range(n):
            below = {k for k in result if k not in locked and result[k] < MIN_WEIGHT}
            if not below:
                break
            locked.update(below)
            for k in below:
                result[k] = MIN_WEIGHT
            locked_budget = MIN_WEIGHT * len(locked)
            remaining_budget = 1.0 - locked_budget
            unlocked_total = sum(v for k, v in result.items() if k not in locked)
            if unlocked_total > 0 and remaining_budget > 0:
                scale = remaining_budget / unlocked_total
                for k in result:
                    if k not in locked:
                        result[k] *= scale

        return result

    def calibrate_weights(self, days: int = 30) -> dict[str, float]:
        """Recalculate weights based on historical agent accuracy.

        For each agent, look at its signals vs. actual price movement.
        Agents that were more accurate get higher weights.
        Uses exponential smoothing so recent performance matters more.

        Returns the new weight dict.
        """
        try:
            from app.database import get_db
        except ImportError:
            logger.debug("Database not available for calibration")
            return self.get_weights()

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        agent_accuracies: dict[str, tuple[float, int]] = {}

        try:
            with get_db() as conn:
                cur = conn.cursor()

                for agent_name in DEFAULT_WEIGHTS:
                    # Get signal predictions for this agent
                    cur.execute(
                        """
                        SELECT ss.ts, ss.symbol, ss.score, ss.confidence
                        FROM signal_scores ss
                        WHERE ss.signal_type = ?
                          AND ss.ts >= ?
                        ORDER BY ss.ts
                        """,
                        [agent_name, cutoff],
                    )
                    signals = cur.fetchall()
                    if len(signals) < MIN_SAMPLE_COUNT:
                        continue

                    correct = 0
                    total = 0
                    for sig in signals:
                        sig_dict = dict(sig)
                        score = sig_dict["score"]
                        symbol = sig_dict["symbol"]
                        ts = sig_dict["ts"]

                        # Check actual price movement after signal
                        cur.execute(
                            """
                            SELECT price FROM price_ticks
                            WHERE symbol = ? AND ts > ?
                            ORDER BY ts
                            LIMIT 1
                            """,
                            [symbol, ts],
                        )
                        after_row = cur.fetchone()

                        cur.execute(
                            """
                            SELECT price FROM price_ticks
                            WHERE symbol = ? AND ts <= ?
                            ORDER BY ts DESC
                            LIMIT 1
                            """,
                            [symbol, ts],
                        )
                        before_row = cur.fetchone()

                        if not after_row or not before_row:
                            continue

                        price_before = dict(before_row)["price"]
                        price_after = dict(after_row)["price"]
                        if price_before <= 0:
                            continue

                        price_change = (price_after - price_before) / price_before
                        # Signal correct if direction matches
                        if (score > 0 and price_change > 0) or (score < 0 and price_change < 0) or (abs(score) < 0.05 and abs(price_change) < 0.01):
                            correct += 1
                        total += 1

                    if total >= MIN_SAMPLE_COUNT:
                        accuracy = correct / total
                        agent_accuracies[agent_name] = (accuracy, total)

        except Exception as e:
            logger.warning("Calibration query failed: %s", e)
            return self.get_weights()

        if not agent_accuracies:
            logger.info("No sufficient history for calibration, keeping defaults")
            return self.get_weights()

        # Calculate new weights
        new_weights = dict(self._weights)
        for agent_name, (accuracy, sample_count) in agent_accuracies.items():
            raw_weight = accuracy * 2  # scale 0-1 accuracy to 0-2 range
            old_weight = self._weights.get(agent_name, DEFAULT_WEIGHTS.get(agent_name, 0.1))
            # Exponential smoothing
            smoothed = SMOOTHING_ALPHA * raw_weight + (1 - SMOOTHING_ALPHA) * old_weight
            new_weights[agent_name] = smoothed

        normalized = self._normalize_weights(new_weights)

        with self._lock:
            self._weights = normalized
            self._last_calibration = datetime.now(timezone.utc)

        # Persist to DB
        try:
            with get_db() as conn:
                cur = conn.cursor()
                _ensure_ensemble_table()
                for agent_name, weight in normalized.items():
                    acc, sc = agent_accuracies.get(agent_name, (None, None))
                    cur.execute(
                        """
                        INSERT INTO ensemble_weights (agent_name, weight, accuracy, sample_count)
                        VALUES (?, ?, ?, ?)
                        """,
                        [agent_name, weight, acc, sc],
                    )
            logger.info("Ensemble weights calibrated: %s", normalized)
        except Exception as e:
            logger.warning("Failed to persist ensemble weights: %s", e)

        return normalized

    def combine_signals(self, agent_signals: list[AgentSignal]) -> dict:
        """Combine agent signals using current adaptive weights.

        Returns:
            {
                "score": float,        # -1 to 1
                "confidence": float,   # 0 to 1
                "signal": str,         # strong_buy/buy/neutral/sell/strong_sell
                "method": "adaptive_ensemble",
                "weights_used": dict,
                "individual_contributions": dict,
            }
        """
        if not agent_signals:
            return {
                "score": 0.0,
                "confidence": 0.0,
                "signal": "neutral",
                "method": "adaptive_ensemble",
                "weights_used": self.get_weights(),
                "individual_contributions": {},
            }

        weights = self.get_weights()
        weighted_score = 0.0
        total_weight = 0.0
        contributions: dict[str, float] = {}

        for sig in agent_signals:
            w = weights.get(sig.agent_name, MIN_WEIGHT)
            effective_weight = w * sig.confidence
            contribution = sig.score * effective_weight
            weighted_score += contribution
            total_weight += effective_weight
            contributions[sig.agent_name] = round(contribution, 4)

        composite_score = weighted_score / total_weight if total_weight > 0 else 0.0

        # Confidence: weighted average penalized by disagreement
        avg_confidence = sum(s.confidence for s in agent_signals) / len(agent_signals)
        bullish = sum(1 for s in agent_signals if s.score > 0.1)
        bearish = sum(1 for s in agent_signals if s.score < -0.1)
        agreement = max(bullish, bearish) / len(agent_signals)
        confidence = avg_confidence * (0.5 + 0.5 * agreement)

        signal = _score_to_signal(composite_score)

        return {
            "score": round(composite_score, 4),
            "confidence": round(confidence, 3),
            "signal": signal,
            "method": "adaptive_ensemble",
            "weights_used": weights,
            "individual_contributions": contributions,
        }

    def confidence_weighted_vote(self, agent_signals: list[AgentSignal]) -> dict:
        """Alternative: each agent votes, weighted by confidence.

        Each agent casts a vote (bullish=+1, bearish=-1, neutral=0),
        weighted by its confidence. Final score is the normalized sum.
        """
        if not agent_signals:
            return {
                "score": 0.0,
                "confidence": 0.0,
                "signal": "neutral",
                "method": "confidence_vote",
                "votes": {},
            }

        votes: dict[str, float] = {}
        weighted_sum = 0.0
        total_confidence = 0.0

        for sig in agent_signals:
            # Vote direction
            if sig.score > 0.1:
                vote = 1.0
            elif sig.score < -0.1:
                vote = -1.0
            else:
                vote = 0.0

            weighted_vote = vote * sig.confidence
            weighted_sum += weighted_vote
            total_confidence += sig.confidence
            votes[sig.agent_name] = round(weighted_vote, 4)

        score = weighted_sum / total_confidence if total_confidence > 0 else 0.0
        confidence = total_confidence / len(agent_signals) if agent_signals else 0.0

        return {
            "score": round(score, 4),
            "confidence": round(confidence, 3),
            "signal": _score_to_signal(score),
            "method": "confidence_vote",
            "votes": votes,
        }


def _score_to_signal(score: float) -> str:
    """Convert a -1..1 score to a signal label."""
    if score >= 0.5:
        return "strong_buy"
    elif score >= 0.2:
        return "buy"
    elif score <= -0.5:
        return "strong_sell"
    elif score <= -0.2:
        return "sell"
    return "neutral"


# Module-level singleton
_ensemble = SignalEnsemble()
