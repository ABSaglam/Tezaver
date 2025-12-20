"""
MX-26001: Test Changelog Exists
"""

import pytest
from pathlib import Path
from tezaver.version import __version__


class TestChangelogExists:
    """Test CHANGELOG.md exists and has correct format."""
    
    def test_changelog_file_exists(self):
        """Test CHANGELOG.md exists at project root."""
        # Find project root
        current = Path(__file__).resolve()
        project_root = current.parent.parent.parent  # tests/platform/... -> root
        
        changelog = project_root / "CHANGELOG.md"
        
        assert changelog.exists(), "CHANGELOG.md not found at project root"
        
    def test_changelog_contains_current_version(self):
        """Test CHANGELOG.md contains current version heading."""
        current = Path(__file__).resolve()
        project_root = current.parent.parent.parent
        
        changelog = project_root / "CHANGELOG.md"
        content = changelog.read_text()
        
        # Check version heading exists
        assert f"## [{__version__}]" in content or f"## {__version__}" in content
        
    def test_changelog_has_sections(self):
        """Test CHANGELOG.md has proper sections."""
        current = Path(__file__).resolve()
        project_root = current.parent.parent.parent
        
        changelog = project_root / "CHANGELOG.md"
        content = changelog.read_text()
        
        # Check for Turkish section headers
        assert "Eklenenler" in content or "Added" in content
