"""
MX-26001: Test Panel Ops Smoke Reports List
"""

import pytest
import json
from pathlib import Path


def list_smoke_reports(base_path: Path) -> list:
    """List smoke reports from directory."""
    reports = list(base_path.glob("SMOKE_*.json"))
    reports.sort(reverse=True, key=lambda x: x.name)
    return reports


def load_smoke_report(path: Path) -> dict:
    """Load smoke report from file."""
    try:
        return json.loads(path.read_text())
    except:
        return None


class TestPanelOpsSmokeReportsList:
    """Test smoke reports listing in Panel Ops."""
    
    def test_list_smoke_reports_finds_files(self, tmp_path):
        """Test list_smoke_reports finds JSON files."""
        # Create sample reports
        (tmp_path / "SMOKE_1000.json").write_text('{"overall": "PASS"}')
        (tmp_path / "SMOKE_2000.json").write_text('{"overall": "FAIL"}')
        (tmp_path / "OTHER.json").write_text('{}')
        
        reports = list_smoke_reports(tmp_path)
        
        assert len(reports) == 2
        
    def test_list_smoke_reports_sorts_newest_first(self, tmp_path):
        """Test reports are sorted newest first."""
        (tmp_path / "SMOKE_1000.json").write_text('{}')
        (tmp_path / "SMOKE_3000.json").write_text('{}')
        (tmp_path / "SMOKE_2000.json").write_text('{}')
        
        reports = list_smoke_reports(tmp_path)
        
        assert reports[0].name == "SMOKE_3000.json"
        assert reports[1].name == "SMOKE_2000.json"
        assert reports[2].name == "SMOKE_1000.json"
        
    def test_load_smoke_report_parses_json(self, tmp_path):
        """Test load_smoke_report parses JSON."""
        report_path = tmp_path / "SMOKE_1234.json"
        report_path.write_text('{"overall": "PASS", "version": "0.1.0"}')
        
        report = load_smoke_report(report_path)
        
        assert report["overall"] == "PASS"
        assert report["version"] == "0.1.0"
        
    def test_load_smoke_report_handles_invalid_json(self, tmp_path):
        """Test load_smoke_report handles invalid JSON."""
        report_path = tmp_path / "SMOKE_bad.json"
        report_path.write_text('not valid json')
        
        report = load_smoke_report(report_path)
        
        assert report is None
        
    def test_empty_directory_returns_empty_list(self, tmp_path):
        """Test empty directory returns empty list."""
        reports = list_smoke_reports(tmp_path)
        
        assert reports == []
