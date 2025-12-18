# Tezaver Bulut - Exit Profile Bootstrap Tests
"""
Tests for exit profile bootstrap logic.
"""

import pytest
import shutil
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from tezaver.bulut.services.exit_profile_loader import ExitProfileLoader
from tezaver.bulut.core.config import BulutConfig

@pytest.fixture
def clean_dirs(tmp_path):
    # Mock data and resource paths
    data_dir = tmp_path / "data"
    profiles_dir = data_dir / "bulut_rules" / "exit_profiles"
    profiles_dir.mkdir(parents=True)
    
    resource_dir = tmp_path / "resources"
    resource_dir.mkdir()
    
    # Create valid resource
    valid_json = {
        "schema": "exit_profile_v1",
        "profile_id": "test",
        "version": "v1",
        "priority": 1,
        "scope": {},
        "rules": [{"type": "fixed_pct"}]
    }
    with open(resource_dir / "valid.json", "w") as f:
        json.dump(valid_json, f)
        
    return data_dir, profiles_dir, resource_dir

@patch("tezaver.bulut.services.exit_profile_loader.get_data_dir")
@patch("tezaver.bulut.services.exit_profile_loader.get_project_root")
def test_bootstrap_empty_dir(mock_root, mock_data, clean_dirs):
    data_dir, profiles_dir, resource_dir = clean_dirs
    
    # Setup mocks
    mock_data.return_value = data_dir
    # Root should return a path that leads to src/.../resources
    # Since loader code does: root / src / tezaver...
    # We need to construct a fake root structure
    
    # Actually checking loader implementation:
    # resource_dir = get_project_root() / "src" / "tezaver" / "bulut" / "resources" / "exit_profiles_examples"
    
    # So we need mock_root to return a path P such that P/src/... exists?
    # Or strict mocking of glob?
    # Hard to mock complex path traversal with simple return_value if code relies on .exists()
    
    # Let's adjust mock_root to return tmp_path, and create the structure there
    root = clean_dirs[2].parent # tmp_path
    mock_root.return_value = root
    
    # Create structure
    real_res_path = root / "src" / "tezaver" / "bulut" / "resources" / "exit_profiles_examples"
    real_res_path.mkdir(parents=True)
    shutil.copy(clean_dirs[2] / "valid.json", real_res_path / "global_scalp.json")
    
    # Init loader
    config = BulutConfig()
    loader = ExitProfileLoader(config)
    # Re-set profiles dir because __init__ might have used real paths if mocking wasn't active then?
    # No, patch decorators apply for the whole test function.
    # __init__ calls get_data_dir()
    
    # Manually clear the dir because __init__ calls ensure_defaults(force=False) automatically!
    # If we want to test return value, we call it again.
    # But init already ran it.
    
    # Let's verify files are there
    assert (profiles_dir / "global_scalp.json").exists()
    
    # Clean up for second run
    shutil.rmtree(profiles_dir)
    profiles_dir.mkdir()
    
    res = loader.ensure_defaults(force=False)
    assert res["ok"]
    assert res["copied_count"] == 1
    assert (profiles_dir / "global_scalp.json").exists()

@patch("tezaver.bulut.services.exit_profile_loader.get_data_dir")
@patch("tezaver.bulut.services.exit_profile_loader.get_project_root")
def test_bootstrap_existing_no_force(mock_root, mock_data, clean_dirs):
    data_dir, profiles_dir, resource_dir = clean_dirs
    root = clean_dirs[2].parent
    mock_root.return_value = root
    mock_data.return_value = data_dir
    
    real_res_path = root / "src" / "tezaver" / "bulut" / "resources" / "exit_profiles_examples"
    real_res_path.mkdir(parents=True, exist_ok=True)
    shutil.copy(clean_dirs[2] / "valid.json", real_res_path / "global_scalp.json")
    
    # Create existing file with DIFFERENT content
    with open(profiles_dir / "global_scalp.json", "w") as f:
        json.dump({"schema": "exit_profile_v1", "modified": True}, f)
        
    loader = ExitProfileLoader(BulutConfig())
    # Init called ensure_defaults -> skipped logic
    
    res = loader.ensure_defaults(force=False)
    assert res["skipped_existing_count"] > 0
    # Content should be unchanged
    with open(profiles_dir / "global_scalp.json", "r") as f:
        data = json.load(f)
        assert data.get("modified") is True

@patch("tezaver.bulut.services.exit_profile_loader.get_data_dir")
@patch("tezaver.bulut.services.exit_profile_loader.get_project_root")
def test_bootstrap_force_backup(mock_root, mock_data, clean_dirs):
    data_dir, profiles_dir, resource_dir = clean_dirs
    root = clean_dirs[2].parent
    mock_root.return_value = root
    mock_data.return_value = data_dir
    
    real_res_path = root / "src" / "tezaver" / "bulut" / "resources" / "exit_profiles_examples"
    real_res_path.mkdir(parents=True, exist_ok=True)
    shutil.copy(clean_dirs[2] / "valid.json", real_res_path / "global_scalp.json")
    
    # Existing file
    with open(profiles_dir / "global_scalp.json", "w") as f:
        json.dump({"schema": "exit_profile_v1", "old": True}, f)
        
    loader = ExitProfileLoader(BulutConfig())
    
    res = loader.ensure_defaults(force=True)
    assert res["ok"]
    assert res["backup_dir"] is not None
    assert res["copied_count"] == 1
    
    # File overwritten
    with open(profiles_dir / "global_scalp.json", "r") as f:
        data = json.load(f)
        assert "rules" in data # It's the new valid one
    
    # Check backup
    backup_path = Path(res["backup_dir"]) / "global_scalp.json"
    assert backup_path.exists()
    with open(backup_path, "r") as f:
        data = json.load(f)
        assert data.get("old") is True

@patch("tezaver.bulut.services.exit_profile_loader.get_data_dir")
@patch("tezaver.bulut.services.exit_profile_loader.get_project_root")
def test_validation_failure(mock_root, mock_data, clean_dirs):
    data_dir, profiles_dir, resource_dir = clean_dirs
    root = clean_dirs[2].parent
    mock_root.return_value = root
    mock_data.return_value = data_dir
    
    real_res_path = root / "src" / "tezaver" / "bulut" / "resources" / "exit_profiles_examples"
    real_res_path.mkdir(parents=True, exist_ok=True)
    
    # Invalid JSON
    with open(real_res_path / "invalid.json", "w") as f:
        json.dump({"schema": "wrong"}, f)
        
    loader = ExitProfileLoader(BulutConfig())
    # Init calls ensure, will fail silently or log err, but we want to check return
    
    res = loader.ensure_defaults(force=False)
    # Should attempt copy but fail validation
    # If dir is empty (except what init might have tried)
    # Init ran once.
    # If invalid, it wont copy.
    
    # Let's ensure dir is empty before explicit call
    shutil.rmtree(profiles_dir)
    profiles_dir.mkdir()
    
    res = loader.ensure_defaults(force=False)
    assert res["copied_count"] == 0
    assert len(res["errors"]) > 0
    assert not (profiles_dir / "invalid.json").exists()
