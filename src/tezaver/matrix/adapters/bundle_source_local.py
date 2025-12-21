import os
import json
from typing import List, Optional, Tuple
from pathlib import Path
from tezaver.matrix.core.candidate_v1 import ManifestV1, PayloadV1

class LocalBundleSource:
    """
    MXI-1000: Discovers and loads CandidateBundle v1 from local filesystem.
    TR: Yerel dosya sisteminden CandidateBundle v1 paketlerini bulur ve yükler.
    """
    
    def __init__(self, base_path: str = "out/matrix_candidates"):
        self.base_path = Path(base_path)

    def discover_bundles(self) -> List[Path]:
        """Scans for manifest.json files in bundle_v1_* directores."""
        bundles = []
        if not self.base_path.exists():
            return []
            
        # Standard: out/matrix_candidates/{SYMBOL}/{TF}/bundle_v1/{ID}/manifest.json
        # Failed: out/matrix_candidates/_failed/{SYMBOL}/{TF}/bundle_v1/{ID}/manifest.json
        
        # We'll do a recursive search for manifest.json
        for path in self.base_path.rglob("manifest.json"):
            # Ensure it's inside a bundle_v1 structure
            if "bundle_v1" in str(path):
                bundles.append(path.parent)
                
        return bundles

    def load_bundle(self, bundle_dir: Path) -> Tuple[ManifestV1, PayloadV1]:
        """Loads manifest and payload from a bundle directory."""
        manifest_path = bundle_dir / "manifest.json"
        payload_path = bundle_dir / "payload.json"
        
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest missing in {bundle_dir}")
        if not payload_path.exists():
            raise FileNotFoundError(f"Payload missing in {bundle_dir}")
            
        with open(manifest_path, "r") as f:
            manifest_dict = json.load(f)
            from tezaver.matrix.core.candidate_v1 import manifest_from_dict
            manifest = manifest_from_dict(manifest_dict)
            
        with open(payload_path, "r") as f:
            payload_dict = json.load(f)
            from tezaver.matrix.core.candidate_v1 import payload_from_dict
            payload = payload_from_dict(payload_dict)
            
        return manifest, payload
