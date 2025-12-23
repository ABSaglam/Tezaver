"""
Bundle Packer V2 - Story-based Grouping
=======================================

Groups individual bundles into "Bundle Packs" based on shared narrative/scenario.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

from tezaver.foundry.bundle_index import scan_bundles

@dataclass
class BundlePackV2:
    """
    A collection of bundles sharing the same story/scenario.
    """
    version: str = "bundle_pack_v2"
    pack_id: str = "" # e.g. pack_SCENARIO_SURF_20251223
    scenario_id: str = ""
    label: str = ""
    description: str = ""
    risk: str = "Medium"
    bundle_ids: List[str] = field(default_factory=list)
    created_ts_iso: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def create_story_packs(
    bundles_root: str = ".tezaver_matrix/approved_bundles_v1",
    output_dir: str = ".tezaver_matrix/foundry/story_packs"
) -> List[str]:
    """
    Scans all bundles and creates pack files for each unique scenario_id.
    """
    df = scan_bundles(bundles_root)
    if df.empty:
        return []
        
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    # Group by scenario_id
    packs_created = []
    unique_scenarios = df["scenario_id"].unique()
    
    for sid in unique_scenarios:
        if not sid: continue
        
        scenario_df = df[df["scenario_id"] == sid]
        bundle_ids = scenario_df["bundle_id"].tolist()
        
        # Get narrative from first bundle
        first_narrative = scenario_df.iloc[0]["narrative"]
        
        pack = BundlePackV2(
            pack_id=f"pack_{sid}_{datetime.now().strftime('%Y%mod%d')}",
            scenario_id=sid,
            label=first_narrative.get("label", "Unknown Story"),
            description=first_narrative.get("desc", ""),
            risk=first_narrative.get("risk", "Medium"),
            bundle_ids=bundle_ids
        )
        
        pack_file = out_path / f"{sid}.json"
        with open(pack_file, 'w') as f:
            json.dump(pack.to_dict(), f, indent=2)
            
        packs_created.append(str(pack_file))
        
    return packs_created

def load_pack(scenario_id: str, packs_root: str = ".tezaver_matrix/foundry/story_packs") -> Optional[Dict[str, Any]]:
    """Loads a specific story pack."""
    path = Path(packs_root) / f"{scenario_id}.json"
    if path.exists():
        with open(path, 'r') as f:
            return json.load(f)
    return None
