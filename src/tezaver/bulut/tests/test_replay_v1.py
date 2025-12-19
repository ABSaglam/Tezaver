# Tezaver Bulut - Replay Functional Tests
import pytest
import json
import uuid
import datetime
from unittest.mock import MagicMock, patch

from tezaver.bulut.core.replay_collector import ReplayCollectorService
from tezaver.bulut.core.replay_engine import ReplayEngine, ReplayContext
from tezaver.bulut.schemas.replay_v1 import ReplayBundleV1
from tezaver.bulut.core.context import BulutContext, BulutConfig

# --- Fixtures ---

@pytest.fixture
def mock_context():
    cfg = BulutConfig()
    ctx = MagicMock(spec=BulutContext)
    ctx.config = cfg
    ctx.universe_source.get_active_universe.return_value = ["BTCUSDT"]
    ctx.bars_store.get_bars.return_value = [] # Empty bars default
    ctx.persistence._get_conn.return_value.cursor.return_value = MagicMock()
    return ctx

@pytest.fixture
def sample_bundle():
    # Make bars snapshot sufficient for 15m scanner (needs 16 bars)
    bars = []
    base_ts = 1000
    for i in range(20):
        bars.append({"ts": base_ts + i*900000, "o": 10, "h": 12, "l": 9, "c": 11, "v": 100})
        
    return ReplayBundleV1(
        bundle_id="test_bundle",
        cycle_ts="2024-01-01T12:00:00",
        created_ts="2024-01-01T12:05:00",
        universe=["BTCUSDT"],
        bars_snapshot={"BTCUSDT": {"15m": bars}},
        policy_state={"BTCUSDT": {"phase": "IDLE"}},
        active_config_hash="abc",
        active_config_json="{}",
        risk_state_json="{}",
        expected_decision_ids={},
        expected_plans={},
        notes="test"
    )

# --- Tests ---

def test_collector_create_bundle(mock_context):
    collector = ReplayCollectorService(mock_context)
    
    # Mock return values for snapshot
    mock_context.bars_store.get_bars.return_value = [
        MagicMock(ts=1000, o=10, h=12, l=9, c=11, v=100)
    ]
    mock_context.persistence.get_open_position_count.return_value = 1
    mock_context.persistence.get_total_notional.return_value = 100.0  # Must be float
    
    bundle = collector.create_bundle_from_current_state("Test Note")
    
    assert bundle.bundle_id is not None
    assert bundle.universe == ["BTCUSDT"]
    assert bundle.bars_snapshot["BTCUSDT"]["15m"][0]["c"] == 11
    assert "open_positions" in bundle.risk_state_json
    
    # Verify save called
    mock_context.persistence._get_conn.assert_called()

def test_replay_engine_determinism(sample_bundle):
    # This test runs ReplayEngine with a sample bundle.
    engine = ReplayEngine()
    
    # Mock Scanner logic to avoid complex dependencies or needing real bars logic
    # We patch Scanner inside replay_engine
    with patch("tezaver.bulut.engine.scanner.Scanner.scan") as mock_scan:
        # Mock ranking
        ranking_mock = MagicMock()
        mock_scan.return_value = ranking_mock
        
        # We also need to mock Decider.decide to avoid real logic if desired,
        # OR we let real decider run but ensure context has what it needs.
        # Real decider needs RankingSnapshotV1.
        # Let's mock Decider.decide to control output and just test engine flow.
        
        with patch("tezaver.bulut.engine.decider.Decider.decide") as mock_decide:
            mock_plan = MagicMock()
            mock_plan.symbol = "BTCUSDT"
            mock_plan.to_dict.return_value = {"idempotency_key": "plan1"}
            mock_plan.idempotency_key = "plan1"
            mock_decide.return_value = [mock_plan]
            
            # 1. Match Case
            sample_bundle.expected_plans = {"BTCUSDT": {"idempotency_key": "plan1"}}
            result = engine.run_replay(sample_bundle)
            assert result.status == "MATCH"
            
            # 2. Drift Case
            sample_bundle.expected_plans = {"BTCUSDT": {"idempotency_key": "plan_diff"}}
            result = engine.run_replay(sample_bundle)
            assert result.status == "DRIFT"
            assert "BTCUSDT" in result.drift_details
