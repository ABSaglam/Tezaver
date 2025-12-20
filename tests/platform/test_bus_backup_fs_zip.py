"""
MX-25004: Test Bus Backup FS Zip
"""

import pytest
import json
import zipfile
from pathlib import Path
from tezaver.platform.cli.bus_backup_cli import backup_fs_bus


class TestBusBackupFsZip:
    """Test FS bus backup to zip."""
    
    def test_backup_creates_zip(self, tmp_path):
        """Test backup creates zip file."""
        bus_root = tmp_path / "bus"
        bus_root.mkdir()
        
        # Create some artifacts
        (bus_root / "artifacts" / "mac").mkdir(parents=True)
        (bus_root / "artifacts" / "mac" / "test.json").write_text('{"test": true}')
        (bus_root / "events").mkdir()
        (bus_root / "events" / "mac.ndjson").write_text('{"kind": "TEST"}\n')
        
        output = tmp_path / "backup.zip"
        
        result = backup_fs_bus(str(bus_root), str(output))
        
        assert result["ok"] is True
        assert output.exists()
        
    def test_backup_contains_files(self, tmp_path):
        """Test backup contains expected files."""
        bus_root = tmp_path / "bus"
        bus_root.mkdir()
        
        (bus_root / "artifacts" / "mac").mkdir(parents=True)
        (bus_root / "artifacts" / "mac" / "test.json").write_text('{"test": true}')
        
        output = tmp_path / "backup.zip"
        
        backup_fs_bus(str(bus_root), str(output))
        
        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert any("test.json" in n for n in names)
            assert any("_backup_manifest.json" in n for n in names)
            
    def test_backup_manifest_has_metadata(self, tmp_path):
        """Test backup manifest contains metadata."""
        bus_root = tmp_path / "bus"
        bus_root.mkdir()
        
        (bus_root / "artifacts").mkdir()
        (bus_root / "artifacts" / "x.json").write_text("{}")
        
        output = tmp_path / "backup.zip"
        
        backup_fs_bus(str(bus_root), str(output))
        
        with zipfile.ZipFile(output, "r") as zf:
            manifest = json.loads(zf.read("_backup_manifest.json"))
            assert "backup_ts" in manifest
            assert "files_count" in manifest
            assert manifest["backup_version"] == "1"
            
    def test_backup_nonexistent_bus_fails(self, tmp_path):
        """Test backup of nonexistent bus fails."""
        result = backup_fs_bus("/nonexistent/path", str(tmp_path / "backup.zip"))
        
        assert result["ok"] is False
        assert "error" in result
