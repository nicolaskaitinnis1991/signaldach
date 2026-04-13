"""Tests for the Signal Ensemble with adaptive weights."""

import math
import pytest

from app.ai.agents.base import AgentSignal
from app.ai.signal_ensemble import (
    DEFAULT_WEIGHTS,
    MIN_WEIGHT,
    SignalEnsemble,
    _ensure_ensemble_table,
)
from app.database import get_db


def _make_signal(agent_name: str, score: float, confidence: float = 0.7) -> AgentSignal:
    """Helper to create test AgentSignal instances."""
    signal = "bullish" if score > 0.1 else ("bearish" if score < -0.1 else "neutral")
    return AgentSignal(
        agent_name=agent_name,
        symbol="BTC/USDT",
        signal=signal,
        confidence=confidence,
        score=score,
        reasoning=f"Test signal from {agent_name}",
    )


class TestDefaultWeights:

    def test_default_weights_sum_to_one(self):
        """Default weights should sum to 1.0."""
        total = sum(DEFAULT_WEIGHTS.values())
        assert math.isclose(total, 1.0, rel_tol=1e-6)

    def test_get_weights_returns_dict(self):
        """get_weights returns a dict with all agent names."""
        ensemble = SignalEnsemble()
        weights = ensemble.get_weights()
        assert isinstance(weights, dict)
        for agent in DEFAULT_WEIGHTS:
            assert agent in weights


class TestCombineSignals:

    def test_combine_signals_basic(self):
        """Basic signal combination produces a valid result."""
        ensemble = SignalEnsemble()
        signals = [
            _make_signal("sentiment", 0.5, 0.8),
            _make_signal("technical", 0.3, 0.9),
            _make_signal("onchain", 0.1, 0.6),
        ]
        result = ensemble.combine_signals(signals)
        assert "score" in result
        assert "confidence" in result
        assert "method" in result
        assert result["method"] == "adaptive_ensemble"
        assert -1.0 <= result["score"] <= 1.0
        assert 0.0 <= result["confidence"] <= 1.0

    def test_combine_signals_empty(self):
        """Empty signal list returns neutral."""
        ensemble = SignalEnsemble()
        result = ensemble.combine_signals([])
        assert result["score"] == 0.0
        assert result["confidence"] == 0.0
        assert result["signal"] == "neutral"

    def test_combine_with_confidence(self):
        """Higher confidence agents contribute more to the result."""
        ensemble = SignalEnsemble()
        # High-confidence bullish vs low-confidence bearish
        signals_high_bull = [
            _make_signal("sentiment", 0.8, 0.95),
            _make_signal("technical", -0.2, 0.1),
        ]
        result = ensemble.combine_signals(signals_high_bull)
        # The bullish signal should dominate due to higher confidence
        assert result["score"] > 0

    def test_individual_contributions_present(self):
        """Result includes individual_contributions dict."""
        ensemble = SignalEnsemble()
        signals = [_make_signal("sentiment", 0.5, 0.8)]
        result = ensemble.combine_signals(signals)
        assert "individual_contributions" in result
        assert "sentiment" in result["individual_contributions"]


class TestConfidenceWeightedVote:

    def test_confidence_weighted_vote(self):
        """Confidence-weighted voting produces valid results."""
        ensemble = SignalEnsemble()
        signals = [
            _make_signal("sentiment", 0.6, 0.9),
            _make_signal("technical", -0.3, 0.5),
            _make_signal("onchain", 0.4, 0.7),
        ]
        result = ensemble.confidence_weighted_vote(signals)
        assert "score" in result
        assert "method" in result
        assert result["method"] == "confidence_vote"
        assert "votes" in result

    def test_confidence_weighted_vote_empty(self):
        """Empty signals produce neutral vote."""
        ensemble = SignalEnsemble()
        result = ensemble.confidence_weighted_vote([])
        assert result["score"] == 0.0
        assert result["signal"] == "neutral"


class TestCalibration:

    def test_calibrate_weights_no_data(self):
        """Calibration with no signal history returns current defaults."""
        ensemble = SignalEnsemble()
        result = ensemble.calibrate_weights(days=30)
        # Should return current weights (defaults) since no data
        assert isinstance(result, dict)
        total = sum(result.values())
        assert math.isclose(total, 1.0, rel_tol=1e-2)


class TestWeightConstraints:

    def test_minimum_weight_enforced(self):
        """No agent weight should fall below MIN_WEIGHT after normalization."""
        ensemble = SignalEnsemble()
        # Manually set very skewed weights
        test_weights = {
            "sentiment": 0.0,
            "technical": 10.0,
            "onchain": 0.0,
            "regulatory": 0.0,
            "anomaly": 0.0,
        }
        normalized = ensemble._normalize_weights(test_weights)
        for w in normalized.values():
            assert w >= MIN_WEIGHT

    def test_weights_normalize_to_one(self):
        """After normalization, weights sum to ~1.0."""
        ensemble = SignalEnsemble()
        test_weights = {
            "sentiment": 0.5,
            "technical": 0.3,
            "onchain": 0.1,
            "regulatory": 0.05,
            "anomaly": 0.05,
        }
        normalized = ensemble._normalize_weights(test_weights)
        total = sum(normalized.values())
        assert math.isclose(total, 1.0, rel_tol=1e-6)


class TestEnsembleWeightsTable:

    def test_ensemble_weights_table_created(self):
        """ensemble_weights table exists after _ensure_ensemble_table()."""
        _ensure_ensemble_table()
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ensemble_weights'"
            )
            row = cur.fetchone()
            assert row is not None
