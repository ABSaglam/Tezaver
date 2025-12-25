import os
import json
from typing import List, Optional, Tuple
from pathlib import Path
from tezaver.matrix.core.candidate_v1 import ManifestV1, PayloadV1

class UnsupportedBundleVersion(Exception):
    """Raised when bundle version is not supported."""
    def __init__(self, detected_version: str, bundle_path: str):
        self.detected_version = detected_version
        self.bundle_path = bundle_path
        super().__init__(f"Unsupported bundle version: {detected_version} at {bundle_path}")

class LocalBundleSource:
    """
    MXI-1000: Discovers and loads CandidateBundle v1 from local filesystem.
    MXI-3.1: Legacy bundle detection.
    TR: Yerel dosya sisteminden CandidateBundle v1 paketlerini bulur ve yükler.
    """
    
    def __init__(self, base_path: str = None):
        if base_path:
            self.base_path = Path(base_path)
        else:
            # User Request: Matrix looks ONLY where Publisher throws (Inbox)
            # Default: ~/.tezaver_bus/pipeline/inbox
            home = os.environ.get("TEZAVER_BUS", os.environ.get("HOME", "."))
            # Handle if TEZAVER_BUS is just the root var or full path? 
            # Usually TEZAVER_BUS env var might define the root.
            # Fallback to standard home structure.
            if "TEZAVER_BUS" in os.environ:
                 # If env var is set, verify if it points to root or inbox. Assuming root.
                 self.base_path = Path(os.environ["TEZAVER_BUS"]) / "pipeline" / "inbox"
            else:
                 self.base_path = Path(home) / ".tezaver_bus" / "pipeline" / "inbox"

    def discover_bundles(self) -> List[Path]:
        """Scans for all manifest.json files, excluding _legacy and _fixtures."""
        bundles = []
        if not self.base_path.exists():
            return []
            
        # Exclude _legacy and _fixtures directories
        for path in self.base_path.rglob("manifest.json"):
            path_str = str(path)
            if "/_legacy/" in path_str or "/_fixtures/" in path_str:
                continue
            bundles.append(path.parent)
                
        return bundles

    def load_bundle(self, bundle_dir: Path) -> Tuple[ManifestV1, PayloadV1]:
        """
        Loads manifest and payload from a bundle directory.
        Raises UnsupportedBundleVersion for legacy bundles.
        """
        manifest_path = bundle_dir / "manifest.json"
        payload_path = bundle_dir / "payload.json"
        
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest missing in {bundle_dir}")
        if not payload_path.exists():
            raise FileNotFoundError(f"Payload missing in {bundle_dir}")
        
        # MXI-3.1 + PNL-1100: Check bundle version before full parse (support both keys)
        with open(manifest_path, "r") as f:
            manifest_dict = json.load(f)
        
        bundle_version = manifest_dict.get("bundle_version") or manifest_dict.get("version") or "1.0"
        # User Request: Standardize format. Publisher emits 1.0, so we accept 1.x
        # Allow any 1.x version
        if not str(bundle_version).startswith("1."):
            raise UnsupportedBundleVersion(bundle_version, str(bundle_dir))
            
        from tezaver.matrix.core.candidate_v1 import manifest_from_dict, payload_from_dict
        manifest = manifest_from_dict(manifest_dict)
            
        with open(payload_path, "r") as f:
            payload_dict = json.load(f)
            payload = payload_from_dict(payload_dict)
            
        return manifest, payload
