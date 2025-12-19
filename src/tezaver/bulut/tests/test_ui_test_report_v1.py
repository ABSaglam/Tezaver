# Tezaver Bulut - Test Report UI Tests
"""
Tests for Test Report UI page and endpoint.
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from tezaver.bulut.ui.pages.test_report import parse_junit_xml, get_test_report


def test_parse_junit_xml_basic(tmp_path):
    """Test basic JUnit XML parsing."""
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="bulut" tests="10" failures="2" errors="1" skipped="1">
  <testcase classname="test_foo" name="test_one" time="0.1"/>
  <testcase classname="test_foo" name="test_two" time="0.2">
    <failure message="Assert failed">Traceback...</failure>
  </testcase>
  <testcase classname="test_bar" name="test_three" time="0.3">
    <error message="Import error">Error...</error>
  </testcase>
</testsuite>
"""
    xml_path = tmp_path / "report.xml"
    xml_path.write_text(xml_content)
    
    result = parse_junit_xml(str(xml_path))
    
    assert result["available"] is True
    assert result["total"] == 10
    assert result["failed"] == 2
    assert result["errors"] == 1
    assert result["skipped"] == 1
    assert result["passed"] == 6  # 10 - 2 - 1 - 1
    assert len(result["top_failures"]) == 2


def test_get_test_report_not_available():
    """Test when no report file exists."""
    with patch("tezaver.bulut.ui.pages.test_report.Path") as mock_path:
        # Make path.exists() return False
        mock_path.return_value.exists.return_value = False
        
        result = get_test_report()
        
        assert result["available"] is False
        assert "No test report" in result.get("message", "")


def test_parse_junit_xml_testsuites_format(tmp_path):
    """Test parsing nested testsuites format."""
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="suite1" tests="5" failures="1" errors="0" skipped="0">
    <testcase classname="t1" name="test_a" time="0.1"/>
    <testcase classname="t1" name="test_b" time="0.1">
      <failure message="Failed">...</failure>
    </testcase>
  </testsuite>
  <testsuite name="suite2" tests="3" failures="0" errors="0" skipped="1">
    <testcase classname="t2" name="test_c" time="0.1"/>
  </testsuite>
</testsuites>
"""
    xml_path = tmp_path / "report2.xml"
    xml_path.write_text(xml_content)
    
    result = parse_junit_xml(str(xml_path))
    
    assert result["available"] is True
    assert result["total"] == 8  # 5 + 3
    assert result["failed"] == 1
    assert result["skipped"] == 1
