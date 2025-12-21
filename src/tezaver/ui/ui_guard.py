"""
Unified UI Guard for Matrix Panel
PNL-1010: Provides error boundary decorator for all render functions.
"""
import streamlit as st
import functools
import traceback


def ui_guard(func):
    """
    Decorator that wraps render functions with error boundary.
    On exception: shows st.error, st.exception, and panel_health summary.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            st.error(f"⚠️ {func.__name__} Render Hatası: {e}")
            st.exception(e)
            
            # Show panel health summary
            try:
                from tezaver.matrix.apps.panel_health import run_health_check
                health = run_health_check()
                with st.expander("🏥 Panel Health Summary", expanded=True):
                    st.metric("Discovered", health.get("discovered_count", 0))
                    st.metric("Imported OK", health.get("imported_count", 0))
                    st.metric("Failed", health.get("failed_count", 0))
                    if health.get("errors"):
                        st.caption("**Hatalar:**")
                        for err in health["errors"][:5]:
                            st.caption(f"❌ {err.get('path')}: {err.get('error')}")
            except Exception as health_err:
                st.caption(f"Panel health yüklenemedi: {health_err}")
    return wrapper


def render_data_sources_box(candidates_root: str = None, registry_path: str = None):
    """
    PNL-1000: Standard 'Data Sources' expander for each page.
    Shows configured paths.
    """
    import os
    candidates_root = candidates_root or os.environ.get("MATRIX_CANDIDATES_ROOT", "out/matrix_candidates")
    registry_path = registry_path or "data/matrix/candidates_registry.jsonl"
    runs_registry_path = "data/matrix/runs_registry.jsonl"
    
    with st.expander("📁 Data Sources", expanded=False):
        st.caption(f"**CWD:** `{os.getcwd()}`")
        st.caption(f"**Candidates Root:** `{candidates_root}`")
        st.caption(f"**Candidates Registry:** `{registry_path}`")
        st.caption(f"**Runs Registry:** `{runs_registry_path}`")
