"""
CardGate Unit Tests

Tests for card governance staleness and drift detection.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import json
import tempfile
import os

from tezaver.matrix.live.card_gate import CardGate, CardGateConfig, CardGateResult


class TestCardGateConfig:
    """Test CardGateConfig defaults and overrides."""
    
    def test_default_config(self):
        cfg = CardGateConfig()
        assert cfg.enabled is True
        assert cfg.max_age_hours == 72.0
        assert cfg.enforce_mode == "BLOCK"
        assert cfg.drift_window_bars == 20
        assert cfg.min_pass_rate == 0.20
        assert cfg.force_stale is False
        assert cfg.force_drift is False
    
    def test_custom_config(self):
        cfg = CardGateConfig(
            enabled=False,
            max_age_hours=24.0,
            enforce_mode="WARN",
            force_stale=True,
        )
        assert cfg.enabled is False
        assert cfg.max_age_hours == 24.0
        assert cfg.enforce_mode == "WARN"
        assert cfg.force_stale is True


class TestCardGateResult:
    """Test CardGateResult dataclass."""
    
    def test_default_result(self):
        result = CardGateResult()
        assert result.gate == "NA"
        assert result.allow is True
        assert result.violations == []
        assert result.metrics == {}
    
    def test_to_dict(self):
        result = CardGateResult(
            gate="BLOCK",
            allow=False,
            violations=["STALE_FORCED"],
            metrics={"age_hours": 9999.0}
        )
        d = result.to_dict()
        assert d["gate"] == "BLOCK"
        assert d["allow"] is False
        assert d["violations"] == ["STALE_FORCED"]
        assert d["metrics"]["age_hours"] == 9999.0


class TestCardGate:
    """Test CardGate evaluation logic."""
    
    def test_disabled_gate_returns_na(self):
        """Disabled gate should return NA and allow."""
        cfg = CardGateConfig(enabled=False)
        gate = CardGate(config=cfg)
        
        result = gate.evaluate(
            symbol="BTCUSDT",
            timeframe="15m",
            profile_id="test",
            cell_id="BTCUSDT|15m|test",
            open_rule_mode="CARD_STRICT_WINDOW",
        )
        
        assert result.gate == "NA"
        assert result.allow is True
        assert result.metrics["reason"] == "GATE_DISABLED"
    
    def test_non_card_mode_returns_na(self):
        """Non-CARD_* mode should return NA."""
        gate = CardGate()
        
        result = gate.evaluate(
            symbol="BTCUSDT",
            timeframe="15m",
            profile_id="test",
            cell_id="BTCUSDT|15m|test",
            open_rule_mode="AUTO_OPEN_FLAT",  # Not CARD_*
        )
        
        assert result.gate == "NA"
        assert result.allow is True
        assert "MODE_AUTO_OPEN_FLAT_NOT_CARD" in result.metrics["reason"]
    
    def test_force_stale_block(self):
        """Force stale should trigger BLOCK with STALE_FORCED violation."""
        events = []
        cfg = CardGateConfig(enforce_mode="BLOCK", force_stale=True)
        gate = CardGate(config=cfg, event_sink=events.append)
        
        result = gate.evaluate(
            symbol="BTCUSDT",
            timeframe="15m",
            profile_id="test",
            cell_id="BTCUSDT|15m|test",
            open_rule_mode="CARD_STRICT_WINDOW",
        )
        
        assert result.gate == "BLOCK"
        assert result.allow is False
        assert "STALE_FORCED" in result.violations
        assert result.metrics["age_hours"] == 9999.0
        
        # Check telemetry emitted
        assert len(events) == 1
        assert events[0]["event_type"] == "CARD_GATE_EVAL"
        assert events[0]["gate"] == "BLOCK"
        assert "REBUILD_CARD" in events[0]["suggested_actions"]
    
    def test_force_stale_warn(self):
        """Force stale with WARN mode should allow but emit warning."""
        cfg = CardGateConfig(enforce_mode="WARN", force_stale=True)
        gate = CardGate(config=cfg)
        
        result = gate.evaluate(
            symbol="BTCUSDT",
            timeframe="15m",
            profile_id="test",
            cell_id="BTCUSDT|15m|test",
            open_rule_mode="CARD_STRICT_WINDOW",
        )
        
        assert result.gate == "WARN"
        assert result.allow is True  # WARN mode allows
        assert "STALE_FORCED" in result.violations
    
    def test_force_drift_block(self):
        """Force drift should trigger BLOCK with DRIFT_FORCED violation."""
        events = []
        cfg = CardGateConfig(enforce_mode="BLOCK", force_drift=True)
        gate = CardGate(config=cfg, event_sink=events.append)
        
        result = gate.evaluate(
            symbol="BTCUSDT",
            timeframe="15m",
            profile_id="test",
            cell_id="BTCUSDT|15m|test",
            open_rule_mode="CARD_STRICT_WINDOW",
        )
        
        assert result.gate == "BLOCK"
        assert result.allow is False
        assert "DRIFT_FORCED" in result.violations
        assert result.metrics["pass_rate"] == 0.0
        
        # Check suggested actions
        assert "LOWER_MIN_PASS_RATE" in events[0]["suggested_actions"]
    
    def test_card_not_found(self):
        """Missing card file should trigger CARD_NOT_FOUND violation."""
        cfg = CardGateConfig(enforce_mode="BLOCK")
        gate = CardGate(config=cfg)
        
        result = gate.evaluate(
            symbol="NONEXISTENT",
            timeframe="99m",
            profile_id="test",
            cell_id="NONEXISTENT|99m|test",
            open_rule_mode="CARD_STRICT_WINDOW",
        )
        
        assert result.gate == "BLOCK"
        assert result.allow is False
        assert "CARD_NOT_FOUND" in result.violations
    
    def test_pass_rate_tracking(self):
        """Test drift tracking via record_tick and get_pass_rate."""
        cfg = CardGateConfig(drift_window_bars=5, min_pass_rate=0.4)
        gate = CardGate(config=cfg)
        
        cell_id = "TEST|1m|test"
        
        # Initially no history -> pass_rate = 1.0
        assert gate.get_pass_rate(cell_id) == 1.0
        
        # Record some ticks
        gate.record_tick(cell_id, True)
        gate.record_tick(cell_id, True)
        gate.record_tick(cell_id, False)
        gate.record_tick(cell_id, False)
        gate.record_tick(cell_id, False)
        
        # 2/5 = 0.4 pass_rate
        assert gate.get_pass_rate(cell_id) == 0.4
        
        # One more False -> 1/5 = 0.2
        gate.record_tick(cell_id, False)
        assert gate.get_pass_rate(cell_id) == 0.2  # Now below threshold
    
    def test_last_results_tracking(self):
        """Test that last_results are tracked per cell."""
        cfg = CardGateConfig(force_stale=True)  # Force a result to be stored
        gate = CardGate(config=cfg)
        
        gate.evaluate("BTC", "1m", "p1", "BTC|1m|p1", "CARD_STRICT_WINDOW")
        gate.evaluate("ETH", "15m", "p2", "ETH|15m|p2", "CARD_STRICT_WINDOW")
        
        results = gate.last_results
        assert "BTC|1m|p1" in results
        assert "ETH|15m|p2" in results


class TestCardGateWithRealCard:
    """Tests that require a real card file."""
    
    @pytest.fixture
    def temp_card_dir(self, tmp_path):
        """Create a temporary card directory with a valid card."""
        card_dir = tmp_path / "data" / "coin_profiles" / "TESTCOIN" / "1m"
        card_dir.mkdir(parents=True)
        
        card = {
            "version": "sniper_strategy_card_v1",
            "card_version": "v1.1",
            "card_build_ts": datetime.now().isoformat(timespec="seconds"),
            "profile_id": "TESTCOIN_1m_test",
            "symbol": "TESTCOIN",
            "timeframe": "1m",
        }
        
        card_path = card_dir / "sniper_strategy_card_v1.json"
        with open(card_path, "w") as f:
            json.dump(card, f)
        
        return tmp_path
    
    def test_pass_with_valid_card(self, temp_card_dir, monkeypatch):
        """Valid card should result in PASS."""
        # Patch the card paths
        monkeypatch.setattr(
            CardGate, 
            "CARD_PATHS", 
            [str(temp_card_dir / "data" / "coin_profiles" / "{symbol}" / "{timeframe}" / "sniper_strategy_card_v1.json")]
        )
        
        cfg = CardGateConfig(enabled=True, enforce_mode="BLOCK")
        gate = CardGate(config=cfg)
        
        result = gate.evaluate(
            symbol="TESTCOIN",
            timeframe="1m",
            profile_id="test",
            cell_id="TESTCOIN|1m|test",
            open_rule_mode="CARD_STRICT_WINDOW",
        )
        
        assert result.gate == "PASS"
        assert result.allow is True
        assert result.violations == []
        assert result.metrics["has_card"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
