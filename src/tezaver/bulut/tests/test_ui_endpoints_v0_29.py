import pytest
import datetime
from unittest.mock import MagicMock, patch
from tezaver.bulut.api.routes_ui import get_ui_summary, get_bars_series, get_audit_latest

@pytest.mark.asyncio
async def test_ui_summary_endpoint():
    # Mock context services
    with patch("tezaver.bulut.api.routes_ui.get_context") as mock_get_ctx:
        ctx = MagicMock()
        mock_get_ctx.return_value = ctx
        
        ctx.persistence.get_open_positions.return_value = []
        ctx.persistence.get_latest_plans.return_value = []
        ctx.config.mode = "TEST"
        ctx.execution_service.is_armed.return_value = False
        
        # Call handler directly
        data = await get_ui_summary()
        
        assert "positions_open" in data
        assert "plans_latest" in data
        assert "status" in data
        assert data["status"]["mode"] == "TEST"

@pytest.mark.asyncio
async def test_audit_endpoint():
    with patch("tezaver.bulut.api.routes_ui.get_context") as mock_get_ctx:
        ctx = MagicMock()
        mock_get_ctx.return_value = ctx
        ctx.persistence.get_latest_audit.return_value = [{"id": 1, "symbol": "BTCUSDT"}]
        
        data = await get_audit_latest()
        assert len(data) == 1
        assert data[0]["symbol"] == "BTCUSDT"
        
@pytest.mark.asyncio
async def test_bars_series_missing_store():
    # If bars_store not mocked/avail
    with patch("tezaver.bulut.api.routes_ui.get_context") as mock_get_ctx:
        ctx = MagicMock()
        mock_get_ctx.return_value = ctx
        
        # Simulate missing store
        del ctx.bars_store 
        
        data = await get_bars_series("BTCUSDT")
        assert "error" in data

@pytest.mark.asyncio
async def test_bars_series_success():
    with patch("tezaver.bulut.api.routes_ui.get_context") as mock_get_ctx:
        ctx = MagicMock()
        mock_get_ctx.return_value = ctx
        
        ctx.bars_store.get_series.return_value = [{"ts": "2023..."}]
        
        data = await get_bars_series("BTCUSDT")
        assert len(data) == 1


