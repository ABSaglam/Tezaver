# Tezaver Bulut - Execution Reliability Tests (v0.14)
"""
Tests for Atomic Execution Locking and Ambiguous Resolution.
"""

import pytest
import sqlite3
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.engine.executor import Executor
from tezaver.bulut.schemas.trade_plan_v1 import TradePlanV1, TradeDecision, TradeSide
from tezaver.bulut.services.idempotency import IdempotencyService
from tezaver.bulut.core.config import BulutConfig

@pytest.fixture
def persistence(tmp_path):
    db_path = tmp_path / "test_exec_v1.db"
    return SqlitePersistence(str(db_path))

@pytest.fixture
def plan():
    # Use from_dict to ensure nested objects (sl/tp) are parsed if needed,
    # or just construct manually. Safer to direct construct if we check types.
    # But usually serialization tests use dict.
    # Let's mock sl/tp to have to_dict() or use types.
    # Simpler: Pass objects if we know them?
    # I'll just use a Mock for 'plan' in most tests or fix the fixture.
    # If I use TradePlanV1, I need Timeframe/Decision enums etc.
    # I'll use from_dict if available.
    
    p = TradePlanV1(
        symbol="BTCUSDT",
        side=TradeSide.LONG,
        decision=TradeDecision.OPEN,
        notional_usdt=100.0,
        sl=MagicMock(),
        tp=MagicMock(),
        reasons={"test": True},
        plan_ts=datetime.now()
    )
    # Mock sl/tp to have value/type for logic
    p.sl.type = "PCT"
    p.sl.value = 1.0
    p.sl.to_dict.return_value = {"type": "PCT", "value": 1.0}
    
    p.tp.type = "PCT"
    p.tp.value = 2.0
    p.tp.to_dict.return_value = {"type": "PCT", "value": 2.0}
    
    return p

def test_atomic_lock(persistence, plan):
    """Test db atomic locking."""
    # Insert plan
    persistence.insert_plan(plan, "ACCEPTED")
    
    # 1. First lock should succeed
    success = persistence.try_mark_executing(plan.idempotency_key)
    assert success is True
    
    # 2. Second lock should fail
    success_2 = persistence.try_mark_executing(plan.idempotency_key)
    assert success_2 is False
    
    # Check state
    conn = persistence._get_conn()
    c = conn.cursor()
    c.execute("SELECT exec_state FROM trade_plans WHERE idempotency_key=?", (plan.idempotency_key,))
    row = c.fetchone()
    assert row[0] == "EXECUTING"
    conn.close()

def test_executor_skips_locked(persistence, plan):
    """Test executor skips if locked."""
    async def run():
        # Setup Executor with mocks
        config = BulutConfig()
        ctx = MagicMock()
        ctx.persistence = persistence
        ctx.bars_store.get_last_closed.return_value = MagicMock(c=50000.0)
        ctx.config = config
        
        executor = Executor(config)
        executor._client = AsyncMock()
        
        # Pre-lock manually
        persistence.insert_plan(plan, "ACCEPTED")
        persistence.try_mark_executing(plan.idempotency_key)
        
        # Execute
        await executor._execute_single_plan(plan, ctx)
        
        # Verify NO calls to client (skipped)
        executor._client.create_order.assert_not_called()
        
    asyncio.run(run())

def test_ambiguous_resolution_found(persistence, plan):
    """Test resolution where order is found on exchange."""
    async def run():
        config = BulutConfig(order_type="MARKET")
        ctx = MagicMock()
        ctx.persistence = persistence
        ctx.bars_store.get_last_closed.return_value = MagicMock(c=50000.0)
        ctx.config = config
        ctx.telemetry = MagicMock()
        
        executor = Executor(config)
        client = AsyncMock()
        executor._client = client
        
        # Insert plan
        persistence.insert_plan(plan, "ACCEPTED")
        
        # Mock create_order to raise Timeout
        client.create_order.side_effect = Exception("ReadTimeout")
        
        # Mock resolve query to find order
        client.get_order_by_client_id.return_value = {
            "status": "FILLED", 
            "avgPrice": "50000.0",
            "orderId": 12345
        }
        
        # Execute
        await executor._execute_single_plan(plan, ctx)
        
        # Verify flow
        # 1. create_order called
        assert client.create_order.called
        # 2. resolve called
        assert client.get_order_by_client_id.called
        # 3. DB finalized as EXECUTED
        conn = persistence._get_conn()
        c = conn.cursor()
        c.execute("SELECT exec_state FROM trade_plans WHERE idempotency_key=?", (plan.idempotency_key,))
        row = c.fetchone()
        assert row[0] == "EXECUTED"
        
        # 4. Position Upserted (OPEN)
        pos = persistence.get_position(plan.symbol)
        assert pos is not None
        assert pos["status"] == "OPEN"
        
    asyncio.run(run())

def test_ambiguous_resolution_not_found(persistence, plan):
    """Test resolution where order is NOT found (phantom)."""
    async def run():
        config = BulutConfig(order_type="MARKET")
        ctx = MagicMock()
        ctx.persistence = persistence
        ctx.bars_store.get_last_closed.return_value = MagicMock(c=50000.0)
        ctx.config = config
        ctx.telemetry = MagicMock()
        
        executor = Executor(config)
        client = AsyncMock()
        executor._client = client
        
        persistence.insert_plan(plan, "ACCEPTED")
        
        client.create_order.side_effect = Exception("NetworkError")
        
        # Mock resolve query to NOT find order (code -2013 or 404)
        client.get_order_by_client_id.return_value = {"code": -2013, "msg": "Order does not exist"}
        
        await executor._execute_single_plan(plan, ctx)
        
        # Verify FAILED status
        conn = persistence._get_conn()
        c = conn.cursor()
        c.execute("SELECT exec_state, exec_error FROM trade_plans WHERE idempotency_key=?", (plan.idempotency_key,))
        row = c.fetchone()
        assert row[0] == "FAILED"
        assert "NetworkError" in row[1]
        
    asyncio.run(run())
