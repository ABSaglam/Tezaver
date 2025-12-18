import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from tezaver.bulut.services.task_supervisor import TaskSupervisor
from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.services.telemetry_ndjson import NdjsonTelemetry

@pytest.fixture
def mock_deps():
    config = BulutConfig()
    persistence = MagicMock(spec=SqlitePersistence)
    telemetry = MagicMock(spec=NdjsonTelemetry)
    return config, persistence, telemetry

@pytest.mark.asyncio
async def test_supervisor_restarts_crashing_task(mock_deps):
    config, persistence, telemetry = mock_deps
    supervisor = TaskSupervisor(config, persistence, telemetry)
    
    # Mock task that crashes once then runs forever (simulated by sleep)
    attempts = 0
    
    async def crashy_task():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("Boom!")
        return # Finish normally on 2nd attempt for test simplicity?
               # Or sleep?
        
    supervisor.register("crashy", crashy_task)
    
    # Start
    await supervisor.start_all()
    
    # Wait a bit for restart logic
    await asyncio.sleep(0.6) # backoff starts at 0.5s
    
    await supervisor.stop_all()
    
    # Verification
    # Should have called beat with CRASHED
    calls = persistence.beat.call_args_list
    crashed_calls = [c for c in calls if c.kwargs.get("status") == "CRASHED"]
    assert len(crashed_calls) >= 1
    assert attempts >= 2 # 1 crash, 1 restart
    
    # Telemetry emitted
    from unittest.mock import ANY
    telemetry.emit.assert_called_with("TASK_RESTART", ANY)

@pytest.mark.asyncio
async def test_heartbeat_updates(mock_deps):
    config, persistence, telemetry = mock_deps
    supervisor = TaskSupervisor(config, persistence, telemetry)
    
    supervisor.beat("test_task", "Running")
    
    persistence.beat.assert_called_with("test_task", status="OK", detail="Running")
