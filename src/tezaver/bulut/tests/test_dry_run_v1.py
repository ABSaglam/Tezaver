# Tezaver Bulut - Dry Run Logic Tests (P4)
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.dry_run_service import DryRunService
from tezaver.bulut.core.executor_sim import SimulatedExecutor

@pytest.fixture
def mock_context():
    cfg = BulutConfig(dry_run_enabled=True)
    ctx = BulutContext(cfg)
    
    # Mock lazy services
    ctx._persistence = MagicMock()
    ctx._telemetry = MagicMock()
    ctx._universe_source = MagicMock()
    ctx._bars_store = MagicMock()
    ctx._scheduler = MagicMock()
    ctx._strict_timing = MagicMock()
    
    return ctx

@pytest.mark.asyncio
async def test_simulated_executor_opens(mock_context):
    """Verify SimulatedExecutor handles OPEN decisions."""
    from tezaver.bulut.schemas.trade_plan_v1 import TradePlanV1, TradeDecision, TradeSide, StopConfig, StopType
    
    executor = SimulatedExecutor(mock_context.config, mock_context.persistence, mock_context.telemetry)
    
    plan = TradePlanV1(
        idempotency_key="p1",
        symbol="BTCUSDT",
        side=TradeSide.LONG,
        decision=TradeDecision.OPEN,
        notional_usdt=100.0,
        sl=StopConfig(StopType.PCT, 1.0),
        tp=StopConfig(StopType.PCT, 2.0),
        leverage=1
    )
    
    res = await executor.execute_plans([plan])
    
    assert res["executed"] == 1
    assert res["mode"] == "DRY_RUN_SIM"
    
    # Check Persistence Call
    mock_context.persistence.open_position.assert_called_once()
    mock_context.telemetry.emit.assert_called()

@pytest.mark.asyncio
async def test_dry_run_service_flow(mock_context):
    """Verify Dry Run Service logic flow (mocks)."""
    
    # Mock Rest Client
    with patch("tezaver.bulut.services.binance_futures_rest.BinanceFuturesRest") as MockClient:
        client_instance = MockClient.return_value
        # Mock fetch_klines returning list of lists [0:open_time, ..., 6:close_time]
        client_instance.fetch_klines = AsyncMock(return_value=[
            [1000000, 100, 100, 100, 100, 100, 1000000 + 60000, 0, 0, 0, 0, 0], 
            [2000000, 100, 100, 100, 100, 100, 2000000 + 60000, 0, 0, 0, 0, 0],
        ])
        client_instance.create_session = AsyncMock()
        client_instance.close = AsyncMock()
        
        service = DryRunService(mock_context)
        
        # Mock Persistence insert_dry_run on MAIN context
        mock_context.persistence.insert_dry_run = MagicMock()
        
        # Mock Shadow Context creation or internal logic (Difficult to mock inside method)
        # Instead, we rely on the method running without error and calling insert_dry_run.
        # But wait, Shadow Context creates new `SqlitePersistence(":memory:")`.
        # This is real IO. It's fine for unit test.
        # But `shadow_ctx.universe_source` (real) might fail if network.
        # We need to ensure Shadow Context dependencies are safe or mocked?
        # `DryRunService` logic calls `shadow_ctx.universe_source.load()`.
        
        # We can mock `BulutContext` class to return a Mock for shadow context?
        with patch("tezaver.bulut.core.dry_run_service.BulutContext") as MockCtxClass:
            shadow_mock = MagicMock()
            MockCtxClass.return_value = shadow_mock
            
            # Mock Shadow Services
            shadow_mock.config.dry_run_enabled = True
            shadow_mock.strict_timing.on_cycle_attempt.return_value = {"status": "ALLOW"}
            shadow_mock.scheduler._run_cycle_logic = AsyncMock()
            
            run_id = await service.start_run(cycles=2)
            
            # Wait a bit for task? It runs in background.
            # `start_run` creates_task.
            # We can await the task if we extract it or sleep.
            # For testing, we might want to run `task_loop` directly.
            
            await service._task_loop(run_id, 2)
            
            # Verify Main Persistence update
            mock_context.persistence.insert_dry_run.assert_called()
            args = mock_context.persistence.insert_dry_run.call_args[0]
            assert args[0] == run_id
            assert args[1] == "SUCCESS"
            assert args[2]["cycles_processed"] == 2 # 2 klines mocked
