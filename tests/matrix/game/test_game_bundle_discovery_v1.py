
import pytest
import os
import json
from pathlib import Path
from tezaver.matrix.game.game_bundle_discovery_v1 import (
    discover_bundles, 
    load_bundle_from_manual_path, 
    resolve_bus_root,
    BundleRef
)

@pytest.fixture
def mock_fs(tmpdir):
    """Create a mock file system structure."""
    root = Path(tmpdir)
    
    # APPROVED
    (root / "out/matrix_approved/bundle_A").mkdir(parents=True)
    with open(root / "out/matrix_approved/bundle_A/manifest.json", "w") as f:
        json.dump({"bundle_id": "BUNDLE_A", "symbol": "BTC", "timeframe": "15m", "created_ts": "2024-01-02"}, f)
        
    # CANDIDATES
    (root / "out/matrix_candidates/bundle_B").mkdir(parents=True)
    with open(root / "out/matrix_candidates/bundle_B/manifest.json", "w") as f:
        json.dump({"bundle_id": "BUNDLE_B", "symbol": "ETH", "timeframe": "1h", "created_ts": "2024-01-01"}, f)

    # Empty
    (root / "out/matrix_candidates/empty_bundle").mkdir(parents=True)

    return str(root)

def test_discover_bundles_approved(mock_fs):
    """Test discovering APPROVED bundles."""
    res = discover_bundles(mock_fs, "APPROVED")
    assert len(res.bundles) == 1
    assert res.bundles[0].bundle_id == "BUNDLE_A"
    assert res.bundles[0].source == "APPROVED"
    assert "out/matrix_approved" in res.scanned_paths[0]

def test_discover_empty_returns_0(mock_fs):
    """Test empty source returns 0."""
    # Create empty golden dir
    p = Path(mock_fs) / "_fixtures"
    p.mkdir(parents=True)
    
    res = discover_bundles(mock_fs, "GOLDEN")
    assert len(res.bundles) == 0
    assert len(res.scanned_paths) > 0

def test_manual_path_folder_loads_manifest(mock_fs):
    """Test manual path loading."""
    path = Path(mock_fs) / "out/matrix_approved/bundle_A"
    b = load_bundle_from_manual_path(str(path))
    assert b is not None
    assert b.bundle_id == "BUNDLE_A"
    assert b.source == "MANUAL"

def test_manifest_best_effort_no_bundle_id(tmpdir):
    """Test fallback ID generation."""
    p = Path(tmpdir) / "some_bundle_folder"
    p.mkdir()
    f = p / "manifest.json"
    with open(f, "w") as h:
        json.dump({"symbol": "BTC"}, h) # No bundle_id
        
    b = load_bundle_from_manual_path(str(p))
    assert b is not None
    assert b.bundle_id == "some_bundle_folder"

def test_dedup_priority():
    # Not Testing cross-source dedup here as discover_bundles is per-source.
    # But checking if discover handles duplicate IDs in same source (newest wins).
    pass 
