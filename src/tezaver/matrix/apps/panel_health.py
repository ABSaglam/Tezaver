"""
Panel Health Diagnostics Tool
MXI-1500: Diagnoses bundle discovery and parse issues.
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

def run_health_check(candidates_root: str = None, output_path: str = None) -> Dict[str, Any]:
    """
    Scans candidates root for bundles, validates each, and reports issues.
    """
    cwd = os.getcwd()
    candidates_root = candidates_root or os.environ.get("MATRIX_CANDIDATES_ROOT", "out/matrix_candidates")
    output_path = output_path or "data/matrix/panel_health.json"
    
    result = {
        "check_time": datetime.now().isoformat(),
        "cwd": cwd,
        "candidates_root": str(Path(candidates_root).absolute()),
        "discovered_count": 0,
        "imported_count": 0,
        "failed_count": 0,
        "errors": [],
        "bundles": []
    }
    
    root = Path(candidates_root)
    if not root.exists():
        result["errors"].append({"type": "ROOT_MISSING", "path": str(root.absolute())})
        _save_result(result, output_path)
        return result
    
    # Discovery: find all manifest.json files (excluding _legacy and _fixtures)
    all_manifests = list(root.rglob("manifest.json"))
    manifests = []
    for m in all_manifests:
        path_str = str(m)
        if "/_legacy/" in path_str or "/_fixtures/" in path_str or "/_failed/" in path_str:
            continue
        manifests.append(m)
    result["discovered_count"] = len(manifests)
    
    for mpath in manifests:
        bundle_dir = mpath.parent
        bundle_info = {"path": str(bundle_dir), "status": "OK", "error": None}
        
        try:
            with open(mpath, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            
            # Check payload
            payload_path = bundle_dir / "payload.json"
            if not payload_path.exists():
                raise FileNotFoundError(f"payload.json missing in {bundle_dir}")
            
            with open(payload_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            
            # Validate minimum fields
            if "bundle_id" not in manifest:
                raise ValueError("manifest missing 'bundle_id'")
            # Support both 'stories' and 'rally_stories_v1' keys
            stories_key = "stories" if "stories" in payload else "rally_stories_v1"
            if stories_key not in payload:
                raise ValueError("payload missing 'stories' or 'rally_stories_v1'")
            
            bundle_info["bundle_id"] = manifest.get("bundle_id")
            bundle_info["story_count"] = len(payload.get(stories_key, []))
            result["imported_count"] += 1
            
        except Exception as e:
            bundle_info["status"] = "FAILED"
            bundle_info["error"] = str(e)
            result["failed_count"] += 1
            result["errors"].append({"path": str(bundle_dir), "error": str(e)})
        
        result["bundles"].append(bundle_info)
    
    _save_result(result, output_path)
    return result

def _save_result(result: Dict, path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

def print_summary(result: Dict):
    print("=== Panel Health Summary ===")
    print(f"CWD: {result['cwd']}")
    print(f"Candidates Root: {result['candidates_root']}")
    print(f"Discovered: {result['discovered_count']}")
    print(f"Imported OK: {result['imported_count']}")
    print(f"Failed: {result['failed_count']}")
    if result['errors']:
        print("First 5 Errors:")
        for err in result['errors'][:5]:
            print(f"  - {err.get('path')}: {err.get('error')}")
    else:
        print("No errors found.")

if __name__ == "__main__":
    result = run_health_check()
    print_summary(result)
