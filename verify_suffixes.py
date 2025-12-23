
from tezaver.matrix.sniper.certification_registry import (
    CertificationRegistry, 
    STAGE_CANDIDATE, STAGE_SNIPER_PASSED, STAGE_LIVE_CERTIFIED, STAGE_VETERAN
)

def test_suffixes():
    print("--- Testing Dynamic Suffixes (-S, -SW, -SWL) ---")
    reg = CertificationRegistry()
    
    bid = "test_suffix_bundle"
    
    # 1. Candidate (No Suffix)
    reg.reset_bundle(bid)
    qid = reg.get_qualified_id(bid)
    print(f"Candidate: {qid}")
    assert qid == bid
    
    # 2. Sniper Passed (-S)
    reg.certify_sniper_pass(bid, "Test")
    qid = reg.get_qualified_id(bid)
    print(f"Sniper Passed: {qid}")
    assert qid == f"{bid}-S"
    
    # 3. Live Certified/War Passed (-SW)
    reg.certify_live_ready(bid, "Test")
    qid = reg.get_qualified_id(bid)
    print(f"Live Certified: {qid}")
    assert qid == f"{bid}-SW"
    
    # 4. Veteran (-SWL)
    reg.certify_veteran(bid, "Test")
    qid = reg.get_qualified_id(bid)
    print(f"Veteran: {qid}")
    assert qid == f"{bid}-SWL"
    
    print("\n✅ All Suffixes Verified!")

if __name__ == "__main__":
    test_suffixes()
