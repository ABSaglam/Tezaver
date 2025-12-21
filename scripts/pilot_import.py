
import os
import json
from pathlib import Path
from tezaver.matrix.adapters.candidate_registry import CandidateRegistry
from tezaver.matrix.adapters.candidate_store_fs import FileCandidateStore
from tezaver.matrix.ports.candidate_bundle import CandidateBundle, RallyStory, Phase, Anchors, bundle_to_dict

def run_import():
    # 1. Sources & Registry
    # Use DEFAULT registry path (data/matrix/candidates_registry.jsonl)
    registry = CandidateRegistry() 
    c_store = FileCandidateStore(home=".") # Use current dir as home for candidates/ dir
    
    root = "out/matrix_candidates"
    bdir = os.path.join(root, "BTCUSDT/15m/bundle_v1")
    if not os.path.exists(bdir):
        print(f"Error: {bdir} not found")
        return
        
    try:
        with open(os.path.join(bdir, "manifest.json")) as f:
            m_dict = json.load(f)
        with open(os.path.join(bdir, "payload.json")) as f:
            p_dict = json.load(f)
        
        stories_data = p_dict.get('rally_stories_v1', [])
        if not stories_data:
            print("No stories found in pilot bundle")
            return
            
        s_data = stories_data[0]
        
        story = RallyStory(
            phases=[Phase(name="Full", start_bar=0, end_bar=100)],
            anchors=Anchors(entry_bar=50, invalidation_bar=0),
            tags=s_data.get('spirit', {}).get('tags', []),
            signatures=s_data.get('signatures', {})
        )
        
        bundle = CandidateBundle(
            symbol=m_dict['symbol'],
            timeframe=m_dict.get('timeframe', m_dict.get('tf', '15m')),
            bundle_version=m_dict['bundle_version'],
            build_ts=m_dict['build_ts'],
            story=story,
            engine_min_version=m_dict.get('engine_min_version', ""),
            data_fingerprint=m_dict.get('data_fingerprint', ""),
            config_signature=m_dict.get('config_signature', ""),
            notes=f"Pilot Run - Story: {s_data.get('story_id')}"
        )
        
        # Consistent ID
        from tezaver.matrix.ports.candidate_bundle import candidate_id as cid_func
        cid = cid_func(bundle)
        
        print(f"Registering Pilot ID: {cid}")
        
        # Save to Registry (data/matrix/candidates_registry.jsonl)
        registry.upsert(
            bundle_id=cid, # Use CID as bundle_id for pilot matching in Sniper
            symbol=bundle.symbol,
            tf=bundle.timeframe,
            bundle_path=str(bdir),
            metrics={
                "trigger_resolve_rate": m_dict.get('trigger_resolve_rate', 0),
                "join_coverage": m_dict.get('join_coverage', 0)
            },
            candidate_id=cid
        )
        
        # Save to Store FS (./candidates/{cid}.json)
        c_store.save(bundle_to_dict(bundle))
        
        print(f"Imported successfully to DEFAULT registry: {cid}")
        
    except Exception as e:
        print(f"Failed pilot import: {e}")

if __name__ == "__main__":
    run_import()
