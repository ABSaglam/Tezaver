
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

def test_candidates_rglob_finds_manifest(mock_fs):
    """Test rglob finding in CANDIDATES."""
    # Add deep bundle
    root = Path(mock_fs)
    deep_path = root / "out/matrix_candidates/Group/SubGroup/DeepBundle/manifest_v2.json"
    deep_path.parent.mkdir(parents=True, exist_ok=True)
    with open(deep_path, "w") as f:
        json.dump({"bundle_id": "DEEP_BUNDLE", "symbol": "SOL", "timeframe": "4h"}, f)
        
    res = discover_bundles(mock_fs, "CANDIDATES")
    # Should find BUNDLE_B (from mock_fs) and DEEP_BUNDLE
    ids = [b.bundle_id for b in res.bundles]
    assert "DEEP_BUNDLE" in ids
    assert "BUNDLE_B" in ids

def test_excludes_legacy_and_failed_by_default(mock_fs):
    """Test default filtering."""
    root = Path(mock_fs)
    # Create legacy
    leg = root / "out/matrix_candidates/_legacy/old_bundle/manifest.json"
    leg.parent.mkdir(parents=True)
    with open(leg, "w") as f:
        json.dump({"bundle_id": "LEGACY_BUNDLE"}, f)
        
    # Create failed
    fail = root / "out/matrix_candidates/_failed/bad_bundle/manifest.json"
    fail.parent.mkdir(parents=True)
    with open(fail, "w") as f:
        json.dump({"bundle_id": "FAILED_BUNDLE"}, f)
        
    # Default: Exclude both
    res = discover_bundles(mock_fs, "CANDIDATES")
    ids = [b.bundle_id for b in res.bundles]
    assert "LEGACY_BUNDLE" not in ids
    assert "FAILED_BUNDLE" not in ids
    assert res.excluded_counts["legacy"] == 1
    assert res.excluded_counts["failed"] == 1
    
    # Include Legacy
    res2 = discover_bundles(mock_fs, "CANDIDATES", include_legacy=True)
    ids2 = [b.bundle_id for b in res2.bundles]
    assert "LEGACY_BUNDLE" in ids2
    assert "FAILED_BUNDLE" not in ids2
    
    # Include Both
    res3 = discover_bundles(mock_fs, "CANDIDATES", include_legacy=True, include_failed=True)
    ids3 = [b.bundle_id for b in res3.bundles]
    assert "LEGACY_BUNDLE" in ids3
    assert "FAILED_BUNDLE" in ids3

def test_approved_missing_reports_missing_root(tmpdir):
    """Test missing root reporting."""
    # Empty dir, no 'out/matrix_approved'
    res = discover_bundles(str(tmpdir), "APPROVED")
    assert len(res.bundles) == 0
    assert len(res.missing_roots) > 0
    assert "matrix_approved" in res.missing_roots[0]

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
