from typing import Dict, List
import copy
from tezaver.matrix.ports.candidate_bundle import CandidateBundle, bundle_from_dict, bundle_to_dict, candidate_id

TF_FACTORS = {
    "15m": 1,
    "1h": 4,
    "4h": 16
}

def compile_story(bundle_dict: Dict, target_timeframe: str) -> Dict:
    """Compiles a candidate story from a lower timeframe to a higher one."""
    
    source_tf = bundle_dict.get("timeframe")
    if source_tf != "15m":
        raise ValueError(f"Story compiler currently supports 15m source only (got {source_tf})")
        
    if target_timeframe not in ["1h", "4h"]:
        raise ValueError(f"Target timeframe must be 1h or 4h (got {target_timeframe})")
        
    factor = TF_FACTORS[target_timeframe] // TF_FACTORS[source_tf]
    
    # Deep copy to safe mutate
    new_bundle = copy.deepcopy(bundle_dict)
    new_bundle["timeframe"] = target_timeframe
    
    # 1. Map Phases
    story = new_bundle.get("story", {})
    source_phases = story.get("phases", [])
    new_phases = []
    
    for p in source_phases:
        new_start = p["start_bar"] // factor
        new_end = p["end_bar"] // factor
        
        # Merge Logic: If same name and overlap/adjacent
        if new_phases:
            last = new_phases[-1]
            if last["name"] == p["name"] and new_start <= last["end_bar"] + 1:
                # Merge
                last["end_bar"] = max(last["end_bar"], new_end)
                continue
                
        new_phases.append({
            "name": p["name"],
            "start_bar": new_start,
            "end_bar": new_end
        })
        
    story["phases"] = new_phases
    
    # 2. Map Anchors
    anchors = story.get("anchors", {})
    if "entry_bar" in anchors:
        anchors["entry_bar"] = anchors["entry_bar"] // factor
    if "invalidation_bar" in anchors:
        anchors["invalidation_bar"] = anchors["invalidation_bar"] // factor
        
    # 3. Update Meta
    # Determinist ID generation relies on bundle content constraints?
    # No, candidate_id comes from properties.
    # Note: signatures are copied as-is (maybe not valid anymore? prompt says copy)
    
    # Add note
    new_bundle["notes"] = f"compiled_from={bundle_dict.get('bundle_version')} factor={factor}"
    
    # Generate ID? Not needed here, caller handles saving.
    return new_bundle
