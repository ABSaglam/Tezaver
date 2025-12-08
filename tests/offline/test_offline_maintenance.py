
"""
Tests for Offline Maintenance Pipeline
"""

import pytest
import time
from unittest.mock import MagicMock, patch
from datetime import datetime

from tezaver.offline.offline_maintenance import (
    OfflineMaintenanceRunner, 
    MaintenanceRunSummary,
    MaintenanceTaskResult
)
# We mock system state recording to avoid disk IO
from tezaver.offline import offline_maintenance

@pytest.fixture
def mock_subprocess():
    with patch("tezaver.offline.offline_maintenance.subprocess.run") as mock:
        yield mock

@pytest.fixture
def mock_record_state():
    with patch("tezaver.offline.offline_maintenance.record_offline_maintenance_run") as mock:
        yield mock

def test_runner_init():
    runner = OfflineMaintenanceRunner(mode="full", symbols=["ETHUSDT"])
    assert runner.mode == "full"
    assert runner.symbols == ["ETHUSDT"]
    assert runner.run_id is not None

def test_run_success(mock_subprocess, mock_record_state):
    """Test a successful run of full pipeline."""
    # Setup mock return for subprocess
    result_ok = MagicMock()
    result_ok.returncode = 0
    mock_subprocess.return_value = result_ok
    
    runner = OfflineMaintenanceRunner(mode="full", symbols=["BTCUSDT"])
    
    summary = runner.run()
    
    assert summary.overall_status == "success"
    assert len(summary.tasks) >= 4 # Fast15, TL 1h, TL 4h, SimAffinity, SimPromo, Radar... at least 4 scripts
    assert mock_record_state.call_count == 1
    
    # Verify task contents
    for t in summary.tasks:
        assert t.status == "success"

def test_run_partial_failure(mock_subprocess, mock_record_state):
    """Test partial failure (one task fails)."""
    
    # We want different side effects for different calls
    # Call 1: Success (Fast15)
    # Call 2: Failure (TL 1h)
    
    res_ok = MagicMock()
    res_ok.returncode = 0
    
    from subprocess import CalledProcessError
    
    def side_effect(*args, **kwargs):
        cmd_list = args[0]
        # Check if the command list contains the specific script we want to fail
        # The runner constructs: [python, path/to/script, --tf, 1h, ...]
        
        cmd_str = " ".join(cmd_list)
        if "run_time_labs_scan.py" in cmd_str and "1h" in cmd_str:
            raise CalledProcessError(returncode=1, cmd=cmd_list, stderr="Mock Error")
        return res_ok
        
    mock_subprocess.side_effect = side_effect
    
    runner = OfflineMaintenanceRunner(mode="full", symbols=["BTCUSDT"])
    summary = runner.run()
    
    assert summary.overall_status == "partial"
    
    # Find the failed task
    failed_tasks = [t for t in summary.tasks if t.status == "failed"]
    assert len(failed_tasks) == 1
    assert failed_tasks[0].name == "Time-Labs 1h"
    assert "Mock Error" in failed_tasks[0].error

def test_run_full_failure(mock_subprocess, mock_record_state):
    """Test full failure."""
    from subprocess import CalledProcessError
    
    def side_effect(*args, **kwargs):
        raise CalledProcessError(returncode=1, cmd=args[0], stderr="Fail")
        
    mock_subprocess.side_effect = side_effect
    
    runner = OfflineMaintenanceRunner(mode="fast", symbols=["BTCUSDT"])
    summary = runner.run()
    
    assert summary.overall_status == "failed"
    for t in summary.tasks:
        assert t.status == "failed"

def test_run_symbol_mode(mock_subprocess, mock_record_state):
    """Test symbol mode passes arguments correctly."""
    mock_subprocess.return_value = MagicMock(returncode=0)
    
    runner = OfflineMaintenanceRunner(mode="symbol", symbols=["ETHUSDT"])
    runner.run()
    
    # Verify args in calls
    # Should see --symbol ETHUSDT in all calls
    for call in mock_subprocess.call_args_list:
        cmd = call[0][0]
        assert "--symbol" in cmd
        assert "ETHUSDT" in cmd
        assert "--all-symbols" not in cmd
