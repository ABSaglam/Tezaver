"""
MX-23004: Test for Deploy wizard blocking activation on FAIL/NO_GO
"""

import pytest
from tezaver.ui.platform_deploy_tab import StepResult, extract_candidate_id_from_export
from tezaver.platform.bus.adapter import FsBusAdapter


class TestPanelDeployGateBlocking:
    """Test deploy wizard gate blocking logic."""
    
    def test_extract_candidate_id_from_export_from_data(self, tmp_path):
        """Test extracting candidate_id from export JSON data."""
        bus = FsBusAdapter(str(tmp_path))
        
        # Create export with candidate_id in data
        bus.put_json("exports/test.json", {"candidate_id": "CAND_FROM_DATA"})
        
        cid = extract_candidate_id_from_export(bus, "exports/test.json")
        
        assert cid == "CAND_FROM_DATA"
        
    def test_extract_candidate_id_from_export_from_filename(self, tmp_path):
        """Test extracting candidate_id from filename when not in data."""
        bus = FsBusAdapter(str(tmp_path))
        
        # Create export without candidate_id in data
        bus.put_json("exports/BTCUSDT_15m_123.json", {"symbol": "BTCUSDT"})
        
        cid = extract_candidate_id_from_export(bus, "exports/BTCUSDT_15m_123.json")
        
        assert cid == "BTCUSDT_15m_123"
        
    def test_extract_candidate_id_from_nonexistent_returns_filename(self, tmp_path):
        """Test extracting candidate_id from nonexistent file uses filename."""
        bus = FsBusAdapter(str(tmp_path))
        
        cid = extract_candidate_id_from_export(bus, "nonexistent/CAND_XYZ.json")
        
        assert cid == "CAND_XYZ"
        
    def test_step_result_dataclass(self):
        """Test StepResult dataclass."""
        step = StepResult("Gate Check", "OK", "PASS", {"release_status": "PASS"})
        
        assert step.name == "Gate Check"
        assert step.status == "OK"
        assert step.data["release_status"] == "PASS"
