"""
MX-25001: Test Panel Connectors Token Mask and Test Connection
"""

import pytest
from unittest.mock import patch, MagicMock
from tezaver.ui.platform_tab import request_with_timeout, ERROR_CODES_TR


class TestRequestWithTimeout:
    """Test request_with_timeout helper."""
    
    def test_success_returns_ok(self):
        """Test successful request returns OK."""
        with patch("tezaver.ui.platform_tab.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"status": "healthy"}'
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            
            result = request_with_timeout("http://localhost/health", "token123")
            
            assert result["ok"] is True
            assert result["error_code"] == "OK"
            assert result["data"]["status"] == "healthy"
            
    def test_401_returns_auth_fail(self):
        """Test 401 response returns AUTH_FAIL."""
        from urllib.error import HTTPError
        
        with patch("tezaver.ui.platform_tab.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = HTTPError(None, 401, "Unauthorized", {}, None)
            
            result = request_with_timeout("http://localhost/health", "bad_token")
            
            assert result["ok"] is False
            assert result["error_code"] == "AUTH_FAIL"
            
    def test_connection_refused_returns_conn_refused(self):
        """Test connection refused returns CONN_REFUSED."""
        from urllib.error import URLError
        
        with patch("tezaver.ui.platform_tab.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = URLError("Connection refused")
            
            result = request_with_timeout("http://localhost:9999/health", "", retries=0)
            
            assert result["ok"] is False
            assert result["error_code"] == "CONN_REFUSED"
            
    def test_timeout_returns_timeout(self):
        """Test timeout returns TIMEOUT."""
        from urllib.error import URLError
        
        with patch("tezaver.ui.platform_tab.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = URLError("timed out")
            
            result = request_with_timeout("http://localhost/health", "", retries=0)
            
            assert result["ok"] is False
            assert result["error_code"] == "TIMEOUT"


class TestErrorCodesTR:
    """Test Turkish error messages."""
    
    def test_auth_fail_has_tr_message(self):
        """Test AUTH_FAIL has Turkish message."""
        assert "AUTH_FAIL" in ERROR_CODES_TR
        assert "Token" in ERROR_CODES_TR["AUTH_FAIL"] or "yetkisiz" in ERROR_CODES_TR["AUTH_FAIL"]
        
    def test_timeout_has_tr_message(self):
        """Test TIMEOUT has Turkish message."""
        assert "TIMEOUT" in ERROR_CODES_TR
        assert "zaman" in ERROR_CODES_TR["TIMEOUT"].lower() or "yanıt" in ERROR_CODES_TR["TIMEOUT"]
        
    def test_conn_refused_has_tr_message(self):
        """Test CONN_REFUSED has Turkish message."""
        assert "CONN_REFUSED" in ERROR_CODES_TR
        assert "bağlan" in ERROR_CODES_TR["CONN_REFUSED"].lower()
