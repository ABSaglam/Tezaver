"""
Core Certification Registry
---------------------------
Registry for managing bundle certification stages.
Stores/Retrieves the lifecycle state (STAGE) of a bundle (Candidate -> Sniper Passed -> Live Certified).
"""
import json
from pathlib import Path
from typing import Dict, Optional
from tezaver.core.stages import STAGE_CANDIDATE, STAGE_SNIPER_PASSED, STAGE_LIVE_CERTIFIED, STAGE_DEMOTED

class CertificationRegistry:
    """
    Manages the certification state of bundles.
    Path: .tezaver_matrix/registry/certifications.json
    """
    
    def __init__(self, registry_path: str = ".tezaver_matrix/registry/certifications.json"):
        self.path = Path(registry_path)
        self._data: Dict[str, str] = {} # bundle_id -> stage
        self._load()

    def _load(self):
        if not self.path.exists():
            self._data = {}
            return

        try:
            with open(self.path, "r") as f:
                self._data = json.load(f)
        except Exception:
            self._data = {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2)

    def get_bundle_stage(self, bundle_id: str) -> str:
        """Get current stage for a bundle. Default: STAGE_CANDIDATE"""
        return self._data.get(bundle_id, STAGE_CANDIDATE)

    def update_stage(self, bundle_id: str, new_stage: str):
        """Update stage for a bundle."""
        self._data[bundle_id] = new_stage
        self._save()

    def list_all(self) -> Dict[str, str]:
        return self._data.copy()
