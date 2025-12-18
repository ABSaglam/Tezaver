# Tezaver Bulut - Bootstrap Test
"""
Tests that context bootstraps correctly without UI.
"""

import pytest
from unittest.mock import patch
import tempfile
import os


def test_bootstrap_context_without_ui():
    """Test that context can bootstrap without Streamlit."""
    # Set up temp paths
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["SQLITE_PATH"] = os.path.join(tmpdir, "test.db")
        os.environ["NDJSON_PATH"] = os.path.join(tmpdir, "events.ndjson")
        os.environ["PATTERN_PACK_DIR"] = os.path.join(tmpdir, "packs")
        
        # Import and bootstrap
        from tezaver.bulut.core.context import bootstrap_context, BulutContext
        from tezaver.bulut.core.config import reload_config
        
        # Reload config with temp paths
        reload_config()
        
        # Bootstrap context
        ctx = bootstrap_context()
        
        # Assertions
        assert isinstance(ctx, BulutContext)
        assert ctx.config is not None
        assert ctx.state is not None
        
        # Check initial state
        assert ctx.state.trade_locked is True
        assert ctx.state.trade_lock_reason == "PATTERN_PACK_MISSING"
        assert ctx.state.pattern_pack_loaded is False
        
        # Check services are accessible
        assert ctx.persistence is not None
        assert ctx.telemetry is not None
        assert ctx.pattern_loader is not None


def test_config_defaults():
    """Test config has correct defaults."""
    from tezaver.bulut.core.config import BulutConfig
    
    # Create fresh config
    config = BulutConfig()
    
    assert config.exchange == "BINANCE"
    assert config.market == "FUTURES"
    assert config.direction == "LONG_ONLY"
    assert config.base_tf == "15m"
    assert config.scan_topk == 20
    assert config.scan_min_score == 70
    assert config.max_open_positions == 3
    assert config.max_total_notional_usdt == 500.0


def test_config_env_override():
    """Test config can be overridden via environment."""
    import os
    
    # Set overrides
    os.environ["SCAN_TOPK"] = "10"
    os.environ["MAX_OPEN_POSITIONS"] = "5"
    
    from tezaver.bulut.core.config import reload_config
    
    config = reload_config()
    
    assert config.scan_topk == 10
    assert config.max_open_positions == 5
    
    # Cleanup
    del os.environ["SCAN_TOPK"]
    del os.environ["MAX_OPEN_POSITIONS"]


def test_no_matrix_imports():
    """Verify no Matrix imports in Bulut modules."""
    import ast
    from pathlib import Path
    
    bulut_dir = Path(__file__).parent.parent
    
    matrix_imports_found = []
    
    for py_file in bulut_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        
        try:
            content = py_file.read_text()
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "matrix" in alias.name.lower():
                            matrix_imports_found.append((py_file, alias.name))
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module and "matrix" in node.module.lower():
                        matrix_imports_found.append((py_file, node.module))
        except:
            pass
    
    assert len(matrix_imports_found) == 0, f"Matrix imports found: {matrix_imports_found}"
