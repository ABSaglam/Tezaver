import pytest
from tezaver.ui.matrix_v4_bridge import parse_debug_build

def test_parse_debug_build_valid():
    """Test parse_debug_build with valid JSON."""
    json_text = '''
    {
        "commit": "abc123",
        "branch": "main",
        "home": "/path/to/home",
        "panel_file": "/path/to/panel.py",
        "counts": {
            "candidates": 5,
            "runs": 10
        }
    }
    '''
    
    result = parse_debug_build(json_text)
    
    assert result["commit"] == "abc123"
    assert result["branch"] == "main"
    assert result["home"] == "/path/to/home"
    assert result["counts"]["candidates"] == 5

def test_parse_debug_build_invalid():
    """Test parse_debug_build with invalid JSON."""
    result = parse_debug_build("not valid json")
    
    assert result == {}

def test_parse_debug_build_empty():
    """Test parse_debug_build with empty string."""
    result = parse_debug_build("")
    
    assert result == {}
