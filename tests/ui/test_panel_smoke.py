"""
PNL-1050: Panel Smoke Tests
Tests that core functions work without streamlit.
UI-level tests require streamlit runtime.
"""
import sys
sys.path.append("src")

# Note: UI smoke tests require streamlit runtime and are skipped in CLI.
# These tests validate core logic only.


def test_panel_health_core():
    """panel_health.py should run without streamlit."""
    try:
        from tezaver.matrix.apps.panel_health import run_health_check, print_summary
        result = run_health_check()
        assert "discovered_count" in result
        assert "imported_count" in result
        assert "failed_count" in result
        print(f"SUCCESS: panel_health runs OK (discovered={result['discovered_count']})")
    except Exception as e:
        print(f"FAIL: {e}")
        raise


def test_bundle_source_local():
    """LocalBundleSource should work without streamlit."""
    try:
        from tezaver.matrix.adapters.bundle_source_local import LocalBundleSource
        source = LocalBundleSource()
        # Just test instantiation and discovery doesn't crash
        bundles = source.discover_bundles()
        print(f"SUCCESS: LocalBundleSource discovers {len(bundles)} bundles")
    except Exception as e:
        print(f"FAIL: {e}")
        raise


def test_candidate_registry():
    """CandidateRegistry should work without streamlit."""
    try:
        from tezaver.matrix.adapters.candidate_registry import CandidateRegistry
        registry = CandidateRegistry()
        cands = registry.list_all()
        print(f"SUCCESS: CandidateRegistry lists {len(cands)} candidates")
    except Exception as e:
        print(f"FAIL: {e}")
        raise


if __name__ == "__main__":
    print("=== PNL-1050: Panel Smoke Tests (Core Only) ===")
    test_panel_health_core()
    test_bundle_source_local()
    test_candidate_registry()
    print("\n=== All smoke tests passed ===")
