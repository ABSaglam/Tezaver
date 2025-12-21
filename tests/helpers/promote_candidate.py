"""
Test Helper: Promote candidate to APPROVED_FOR_WAR status.
For test environment only.
"""
import sys
sys.path.append("src")

from tezaver.matrix.adapters.candidate_registry import CandidateRegistry


def promote_first_candidate_to_war() -> dict:
    """
    Promote the first non-failed candidate to APPROVED_FOR_WAR.
    Returns the promoted candidate dict or None if no candidates.
    """
    registry = CandidateRegistry()
    candidates = registry.list_all()
    
    # Find first candidate that isn't FAILED_IMPORT
    for c in candidates:
        if c.get("status") != "FAILED_IMPORT":
            bundle_id = c.get("bundle_id")
            registry.update_status(bundle_id, "APPROVED_FOR_WAR")
            print(f"Promoted {bundle_id} to APPROVED_FOR_WAR")
            return registry.get(bundle_id)
    
    print("No promotable candidate found")
    return None


def promote_candidate_by_id(bundle_id: str) -> dict:
    """Promote specific candidate to APPROVED_FOR_WAR."""
    registry = CandidateRegistry()
    registry.update_status(bundle_id, "APPROVED_FOR_WAR")
    return registry.get(bundle_id)


def list_candidates_by_status() -> dict:
    """List all candidates grouped by status."""
    registry = CandidateRegistry()
    candidates = registry.list_all()
    
    by_status = {}
    for c in candidates:
        status = c.get("status", "UNKNOWN")
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(c.get("bundle_id"))
    
    return by_status


if __name__ == "__main__":
    print("=== Candidate Status Summary ===")
    by_status = list_candidates_by_status()
    for status, ids in by_status.items():
        print(f"{status}: {len(ids)}")
        for bid in ids[:3]:
            print(f"  - {bid}")
    
    print("\n=== Promoting first candidate ===")
    promoted = promote_first_candidate_to_war()
    if promoted:
        print(f"Result: {promoted}")
