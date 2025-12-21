import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from .fingerprint import calculate_data_fingerprint, calculate_config_signature
from tezaver.version import __version__ as REPO_VERSION

class CandidateBundleExporter:
    """
    Exports CandidateBundle v1 (Manifest + Payload).
    MACX-1020
    """
    
    def __init__(self, output_base: Path):
        self.output_base = output_base
        
    def export_bundle(self, 
                      symbol: str, 
                      timeframe: str,
                      stories: List[Dict[str, Any]],
                      source_files: List[Path],
                      config: Dict[str, Any],
                      metrics: Optional[Dict[str, Any]] = None,
                      diagnostics: Optional[List[Dict]] = None,
                      compiled_stories_1h: Optional[List[Dict]] = None,
                      compiled_stories_4h: Optional[List[Dict]] = None,
                      version_tag: str = "v1") -> Path:
        """
        Creates manifest and payload files in a unique bundle directory.
        MACX-2012, MACX-2014
        """
        bundle_id = f"{symbol}_{timeframe}_bundle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        bundle_dir = self.output_base / symbol / timeframe / f"bundle_{version_tag}"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        
        # Calculate fingerprints
        data_fp = calculate_data_fingerprint(source_files)
        config_sig = calculate_config_signature(config)
        
        # Build Manifest
        manifest = {
            "bundle_id": bundle_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "bundle_version": "1.1.1",
            "build_ts": datetime.now().isoformat(),
            "engine_min_version": REPO_VERSION,
            "data_fingerprint": data_fp,
            "config_signature": config_sig,
            "story_count": len(stories),
            "sources": [str(p) for p in source_files]
        }
        
        # MACX-2012: Add detailed metrics to Manifest
        if metrics:
            manifest.update(metrics)
        
        # Build Payload
        payload = {
            "rally_stories_v1": stories,
            "compiled_stories_1h": compiled_stories_1h or [],
            "compiled_stories_4h": compiled_stories_4h or [],
            "sources": [str(p) for p in source_files],
            "config": config,
            "metadata": {
                "exporter": "CandidateBundleExporter_v1.1",
                "generated_at": datetime.now().isoformat()
            }
        }
        
        # MACX-2014: Write Diagnostics
        if diagnostics:
            diag_path = bundle_dir / "join_diagnostics.json"
            summary = {
                "total_events": len(diagnostics),
                "matched_count": sum(1 for d in diagnostics if d['status'] == 'joined'),
                "unmatched_count": sum(1 for d in diagnostics if d['status'] == 'unmatched'),
                "avg_diff_min": round(sum(d['diff_min'] for d in diagnostics) / len(diagnostics), 2) if diagnostics else 0,
                "details": diagnostics
            }
            with open(diag_path, 'w') as f:
                json.dump(summary, f, indent=2)

        # Write files
        manifest_path = bundle_dir / "manifest.json"
        payload_path = bundle_dir / "payload.json"
        
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            
        with open(payload_path, "w", encoding="utf-8") as f:
            # Use compact JSON for payload to save space if needed, 
            # but user likes readable for now.
            json.dump(payload, f, indent=2, ensure_ascii=False)
            
        return bundle_dir
