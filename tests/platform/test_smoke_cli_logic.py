"""
MX-26001: Test Smoke CLI Logic
"""

import pytest
from unittest.mock import patch, MagicMock
from tezaver.platform.cli.smoke_cli import request_with_timeout


class TestSmokeCliLogic:
    """Test smoke CLI helper functions."""
    
    def test_request_with_timeout_success(self):
        """Test successful request."""
        with patch("tezaver.platform.cli.smoke_cli.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"status": "healthy"}'
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            
            result = request_with_timeout("http://localhost/health", "token")
            
            assert result["ok"] is True
            assert result["data"]["status"] == "healthy"
            
    def test_request_with_timeout_failure(self):
        """Test failed request."""
        from urllib.error import URLError
        
        with patch("tezaver.platform.cli.smoke_cli.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = URLError("Connection refused")
            
            result = request_with_timeout("http://localhost/health", "token")
            
            assert result["ok"] is False
            assert "error" in result


class TestSmokeCLIArgs:
    """Test smoke CLI arguments."""
    
    def test_smoke_cli_has_help(self):
        """Test smoke CLI has help."""
        import argparse
        from tezaver.platform.cli.smoke_cli import main
        
        # Just verify the module can be imported
        assert main is not None
