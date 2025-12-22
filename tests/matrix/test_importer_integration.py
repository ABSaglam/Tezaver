import os
import shutil
from pathlib import Path
from tezaver.matrix.adapters.bundle_source_local import LocalBundleSource
from tezaver.matrix.adapters.candidate_registry import CandidateRegistry

def test_importer_and_registry_flow():
    # 1. Setup paths
    test_registry_path = "data/matrix/test_registry.jsonl"
    if os.path.exists(test_registry_path):
        os.remove(test_registry_path)
        
    source = LocalBundleSource(base_path="out/matrix_candidates")
    registry = CandidateRegistry(registry_path=test_registry_path)
    
    # 2. Discover
    bundles = source.discover_bundles()
    print(f"Discovered {len(bundles)} bundles")
    
    if len(bundles) == 0:
        print("No bundles discovered. Skipping deep test.")
        return
        
    # 3. Import & Register
    bdir = bundles[0]
    manifest, payload = source.load_bundle(bdir)
    
    from tezaver.matrix.core.candidate_v1 import generate_candidate_id
    cid = generate_candidate_id(manifest)
    
    entry = registry.register(
        candidate_id=cid,
        symbol=manifest.symbol,
        tf=manifest.tf,
        bundle_id=manifest.bundle_id,
        bundle_path=str(bdir),
        metrics={
            "trigger_resolve_rate": manifest.metrics.trigger_resolve_rate,
            "join_coverage": manifest.metrics.join_coverage
        }
    )
    
    assert entry["candidate_id"] == cid
    assert entry["symbol"] == manifest.symbol
    assert entry["status"] == "NEW"
    
    # 4. Persistence Test
    # MX-9310: get() uses bundle_id as key
    registry2 = CandidateRegistry(registry_path=test_registry_path)
    assert len(registry2.list_all()) == 1
    assert registry2.get(manifest.bundle_id)["symbol"] == manifest.symbol
    
    print("Integration test PASSED")

if __name__ == "__main__":
    test_importer_and_registry_flow()
