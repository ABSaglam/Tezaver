import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from .fingerprint import calculate_data_fingerprint, calculate_config_signature
from tezaver.version import __version__ as REPO_VERSION
import os
import pandas as pd

class BundleExporter:
    """
    Exports CandidateBundle v1.1.2 to standard disk structure.
    Supports MACX-2140: Fail Artifacts
    """
    def __init__(self, base_dir: str = "out/matrix_candidates"):
        self.base_dir = base_dir

    def export_bundle(self, 
                      symbol: str, 
                      tf: str, 
                      stories: List[Dict], 
                      compiled_stories: Dict,
                      metrics: Dict,
                      diagnostics: List[Dict],
                      fingerprints: Dict,
                      is_failed: bool = False) -> str:
        
        # MACX-2140: Support _failed directory
        sub_dir = "_failed" if is_failed else ""
        bundle_id = f"bundle_v1_{int(pd.Timestamp.now().timestamp())}"
        
        export_path = os.path.join(self.base_dir, sub_dir, symbol, tf, "bundle_v1", bundle_id)
        os.makedirs(export_path, exist_ok=True)
        
        # manifest.json
        manifest = {
            "version": "1.1.2",
            "repo_version": REPO_VERSION,
            "bundle_id": bundle_id,
            "symbol": symbol,
            "tf": tf,
            "export_time_utc": pd.Timestamp.now(tz='UTC').isoformat(),
            "metrics": metrics,
            "fingerprints": fingerprints,
            "status": "failed" if is_failed else "success"
        }
        
        with open(os.path.join(export_path, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=4)
            
        # payload.json
        payload = {
            "stories": stories,
            "compiled_stories": compiled_stories
        }
        with open(os.path.join(export_path, "payload.json"), "w") as f:
            json.dump(payload, f, indent=4)
            
        # MACX-2014: join_diagnostics.json
        with open(os.path.join(export_path, "join_diagnostics.json"), "w") as f:
            json.dump(diagnostics, f, indent=4)
            
        return export_path
