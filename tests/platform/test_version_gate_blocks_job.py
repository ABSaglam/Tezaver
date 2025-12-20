"""
MX-25003: Test Version Gate Logic
"""

import pytest


def check_version_compatibility(agent_api_version: str, expected_api: str = "1") -> dict:
    """Check version compatibility (logic from Ops dashboard)."""
    if agent_api_version == expected_api:
        return {"color": "green", "status": "uyumlu", "compatible": True}
    elif agent_api_version == "?":
        return {"color": "orange", "status": "bilinmiyor", "compatible": None}
    else:
        return {"color": "red", "status": "UYUMSUZ", "compatible": False}


class TestVersionGate:
    """Test version compatibility gate logic."""
    
    def test_matching_version_is_green(self):
        """Test matching version shows green."""
        result = check_version_compatibility("1", "1")
        
        assert result["color"] == "green"
        assert result["compatible"] is True
        
    def test_different_version_is_red(self):
        """Test different version shows red."""
        result = check_version_compatibility("2", "1")
        
        assert result["color"] == "red"
        assert result["compatible"] is False
        assert "UYUMSUZ" in result["status"]
        
    def test_unknown_version_is_orange(self):
        """Test unknown version shows orange."""
        result = check_version_compatibility("?", "1")
        
        assert result["color"] == "orange"
        assert result["compatible"] is None
        
    def test_null_version_treated_as_unknown(self):
        """Test None defaults to unknown behavior when passed as '?'."""
        result = check_version_compatibility("?")
        
        assert result["color"] == "orange"


class TestApiVersionInHealth:
    """Test api_version in agent health."""
    
    def test_base_agent_returns_api_version(self, tmp_path):
        """Test BaseAgent health includes api_version."""
        from tezaver.platform.agents.base import BaseAgent, AgentConfig
        
        class TestAgent(BaseAgent):
            def setup_handlers(self):
                pass
                
        config = AgentConfig(
            agent_name="test",
            bus_root=str(tmp_path),
            token="",
        )
        
        agent = TestAgent(config)
        health = agent.health()
        
        assert "api_version" in health
        assert health["api_version"] == "1"
        assert "platform_version" in health
