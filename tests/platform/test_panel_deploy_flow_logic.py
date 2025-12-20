"""
MX-23003: Test for Panel Deploy Flow Logic
"""

import os
import json
import pytest
from tezaver.platform.bus.adapter import FsBusAdapter
from tezaver.ui.platform_deploy_tab import (
    run_approved_deploy_flow, StepResult, enqueue_job, 
    get_outbox_result, list_exports
)


class TestPanelDeployFlowLogic:
    """Test panel deploy flow logic."""
    
    def test_enqueue_job(self, tmp_path):
        """Test job enqueue creates file in inbox."""
        bus = FsBusAdapter(str(tmp_path))
        
        job_id = enqueue_job(bus, "cloud", "CLOUD_IMPORT_STRATEGY", {"export_path": "test.json"})
        
        assert job_id.startswith("job_")
        assert bus.exists(f"jobs/cloud/inbox/{job_id}.json")
        
    def test_list_exports(self, tmp_path):
        """Test listing export artifacts."""
        bus = FsBusAdapter(str(tmp_path))
        
        # Create some exports
        bus.put_json("artifacts/matrix/exports/exp_001.json", {"id": "001"})
        bus.put_json("artifacts/matrix/exports/exp_002.json", {"id": "002"})
        
        exports = list_exports(bus)
        
        assert len(exports) == 2
        assert any("exp_001.json" in e for e in exports)
        
    def test_list_exports_empty(self, tmp_path):
        """Test listing returns empty when no exports."""
        bus = FsBusAdapter(str(tmp_path))
        
        exports = list_exports(bus)
        
        assert exports == []
        
    def test_step_result_dataclass(self):
        """Test StepResult dataclass."""
        step = StepResult("Import Strategy", "OK", "STRAT_001", {"strategy_id": "STRAT_001"})
        
        assert step.name == "Import Strategy"
        assert step.status == "OK"
        assert step.data["strategy_id"] == "STRAT_001"
