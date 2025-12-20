"""
MX-26001: Test Version Module
"""

import pytest
from tezaver.version import __version__, build_commit, version_string


class TestVersionModule:
    """Test version module."""
    
    def test_version_exists(self):
        """Test __version__ is defined."""
        assert __version__ is not None
        assert isinstance(__version__, str)
        assert len(__version__) > 0
        
    def test_version_format(self):
        """Test version is in semver format."""
        parts = __version__.split(".")
        assert len(parts) == 3
        # Each part should be numeric
        for part in parts:
            assert part.isdigit()
            
    def test_build_commit_returns_string(self):
        """Test build_commit returns a string."""
        commit = build_commit()
        assert isinstance(commit, str)
        assert len(commit) > 0
        
    def test_version_string_includes_version(self):
        """Test version_string includes version."""
        vs = version_string()
        assert __version__ in vs
        assert "Tezaver" in vs
