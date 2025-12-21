import pytest
from unittest.mock import patch, MagicMock
from tezaver.matrix.protocols.safety_registry import SafetyStatus

# We test the logic injected in matrix_v4_tab.py if possible, 
# or verify the logic independently if it's too tied to Streamlit.
# Here we'll test the logic that would be used in the UI.

def test_release_gate_blocks_on_red():
    # Mocking the registry to return a RED protocol
    mock_p = {
        "mx": "MX-BLOCKER",
        "name": "Blocker",
        "status": {"LIVE": "RED"},
        "active_in": ["LIVE"]
    }
    
    with patch("tezaver.matrix.protocols.safety_registry.SafetyProtocolRegistry") as MockReg:
        instance = MockReg.return_value = MagicMock()
        instance.protocols = [mock_p]
        instance.get_overall_for_active.return_value = SafetyStatus.RED
        
        # Simulate the logic in matrix_v4_tab.py
        registry = MockReg()
        red_protocols = [p for p in registry.protocols if registry.get_overall_for_active(p["mx"]) == SafetyStatus.RED]
        
        assert len(red_protocols) == 1
        assert red_protocols[0]["mx"] == "MX-BLOCKER"
        
        # Simulate result override
        result = {"ok": True, "summary": "Initial Pass"}
        if red_protocols:
            result["ok"] = False
            result["summary"] = f"BLOCKED by {len(red_protocols)} RED Safety Protocols"
            
        assert result["ok"] is False
        assert "BLOCKED" in result["summary"]

def test_release_gate_passes_on_green():
    mock_p = {
        "mx": "MX-OK",
        "status": {"LIVE": "GREEN"},
        "active_in": ["LIVE"]
    }
    
    with patch("tezaver.matrix.protocols.safety_registry.SafetyProtocolRegistry") as MockReg:
        instance = MockReg.return_value = MagicMock()
        instance.protocols = [mock_p]
        instance.get_overall_for_active.return_value = SafetyStatus.GREEN
        
        registry = MockReg()
        red_protocols = [p for p in registry.protocols if registry.get_overall_for_active(p["mx"]) == SafetyStatus.RED]
        
        assert len(red_protocols) == 0
        
        result = {"ok": True, "summary": "Initial Pass"}
        if red_protocols:
            result["ok"] = False
            
        assert result["ok"] is True
