import os
import json
import pytest
from tezaver.matrix.core.cloud_import import import_export_package
from tezaver.matrix.core.checksums import write_json

def test_cloud_import_checksum_fail(tmp_path):
    home = str(tmp_path)
    exp_dir = tmp_path / "exports" / "EXPORT_BAD"
    os.makedirs(exp_dir)
    
    # File
    write_json(str(exp_dir / "file1.json"), {"data": "A"})
    
    # Manifest with WRONG SHA (using SHA of "B")
    # Let's just hardcode a mismatch
    manifest = {
        "version": "export_v1",
        "candidate_id": "C1",
        "symbol": "BTC", "timeframe": "1m",
        "files": ["file1.json"],
        "sha256": {"file1.json": "badsha"}
    }
    write_json(str(exp_dir / "export_manifest.json"), manifest)
    
    with pytest.raises(ValueError, match="Checksum mismatch"):
        import_export_package(home, str(exp_dir))
