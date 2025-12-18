# Tezaver Bulut - Universe Source Tests
"""
Tests for UniverseSource service.
"""

import pytest
import tempfile
import os

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.universe_source import UniverseSource

def test_universe_fallback_when_file_missing():
    """Should use fallback list when file is missing."""
    config = BulutConfig(
        universe_path="non_existent_file.txt",
        universe_fallback_symbols=["BTCUSDT", "ETHUSDT"]
    )
    source = UniverseSource(config)
    
    symbols = source.load()
    assert symbols == ["BTCUSDT", "ETHUSDT"]

def test_universe_from_file_with_comments_and_empty_lines():
    """Should load symbols from file, ignoring comments and empty lines."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
        tmp.write("BTCUSDT\n")
        tmp.write("# This is a comment\n")
        tmp.write("\n")
        tmp.write("ETHUSDT\n")
        tmp.write("  # Indented comment\n")
        tmp.write("SOLUSDT") # No newline at end
        tmp_path = tmp.name

    try:
        config = BulutConfig(
            universe_path=tmp_path,
            universe_fallback_symbols=["FAIL"]
        )
        source = UniverseSource(config)
        
        symbols = source.load()
        assert "BTCUSDT" in symbols
        assert "ETHUSDT" in symbols
        assert "SOLUSDT" in symbols
        assert len(symbols) == 3
        assert "FAIL" not in symbols
    finally:
        os.remove(tmp_path)

def test_universe_env_override():
    """Should respect env var overriding path."""
    # Create two temp files
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f1:
        f1.write("FROM_DEFAULT")
        path1 = f1.name
        
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f2:
        f2.write("FROM_ENV")
        path2 = f2.name
        
    try:
        import os
        from tezaver.bulut.core.config import reload_config
        
        os.environ["UNIVERSE_PATH"] = path2
        
        # Reload config to pick up env
        config = reload_config()
        
        # Verify config picked up env
        assert config.universe_path == path2
        
        # Verify source loads from env path
        source = UniverseSource(config)
        symbols = source.load()
        assert symbols == ["FROM_ENV"]
        
    finally:
        os.remove(path1)
        os.remove(path2)
        if "UNIVERSE_PATH" in os.environ:
            del os.environ["UNIVERSE_PATH"]
