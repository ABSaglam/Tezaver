import pytest
import shutil
import resource
from pathlib import Path
from tezaver.matrix.ops.resource_guard import ResourceGuard

def test_resource_guard_ok():
    guard = ResourceGuard(disk_min_mb=1.0, rss_max_mb=10000.0)
    # Assume host is relatively healthy for this test or it might fail
    # But usually it is. 
    res = guard.check_resources(Path("."))
    assert res["ok"] is True
    assert "disk_free_mb" in res["metrics"]

def test_resource_guard_low_disk(monkeypatch):
    monkeypatch.setattr(shutil, "disk_usage", lambda x: type('obj', (object,), {'free': 50 * 1024 * 1024})) # 50MB free
    
    guard = ResourceGuard(disk_min_mb=100.0)
    res = guard.check_resources(Path("."))
    
    assert res["ok"] is False
    assert any("LOW_DISK" in r for r in res["reasons"])

def test_resource_guard_high_rss(monkeypatch):
    # Mock RSS to 3GB
    def mock_rusage(who):
        return type('obj', (object,), {'ru_maxrss': 3000 * 1024 * 1024 if 'darwin' else 3000 * 1024}) # bytes or kb
    
    import sys
    # Actually need to mock the getter in guard or the resource module
    from tezaver.matrix.ops.resource_guard import ResourceGuard
    monkeypatch.setattr(ResourceGuard, "get_rss_mb", lambda x: 3000.0)
    
    guard = ResourceGuard(rss_max_mb=2048.0)
    res = guard.check_resources(Path("."))
    
    assert res["ok"] is False
    assert any("HIGH_RSS" in r for r in res["reasons"])
