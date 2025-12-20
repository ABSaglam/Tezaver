"""
Tezaver Bulut - Build Fingerprint Contract Test
Verifies that the build fingerprint helper captures required fields.
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from tezaver.bulut.ui.contracts.build_fingerprint import get_build_fingerprint

def test_fingerprint_structure():
    """Verify dictionary structure and mandatory fields."""
    fp = get_build_fingerprint()
    assert isinstance(fp, dict)
    assert "build_ts" in fp
    assert "pid" in fp
    assert "watcher_type" in fp
    assert "git_head" in fp
    
    # PID should be int
    assert isinstance(fp["pid"], int) 
    assert fp["pid"] == os.getpid()

def test_fingerprint_git_fallback():
    """Verify behavior when git command fails."""
    with patch("subprocess.check_output") as mock_sub:
        mock_sub.side_effect = Exception("Git not found")
        
        fp = get_build_fingerprint()
        assert fp["git_head"] == "Unknown"

def test_fingerprint_watcher_env():
    """Verify watcher type from env."""
    with patch.dict(os.environ, {"STREAMLIT_SERVER_FILE_WATCHER_TYPE": "poll"}):
        fp = get_build_fingerprint()
        assert fp["watcher_type"] == "poll"
