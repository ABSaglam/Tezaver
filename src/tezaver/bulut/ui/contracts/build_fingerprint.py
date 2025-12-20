"""
Tezaver Bulut - UI Build Fingerprint
Captures runtime environment details for debugging (PID, Git SHA, Watcher).
"""
import os
import datetime
import subprocess

def get_build_fingerprint() -> dict:
    """Returns a dictionary with build and runtime info."""
    
    # 1. Basic Runtime
    info = {
        "build_ts": datetime.datetime.now().isoformat(timespec='seconds'),
        "pid": os.getpid(),
        "watcher_type": os.environ.get("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "(default)"),
        "git_head": None
    }
    
    # 2. Git SHA (Best Effort)
    try:
        # Run git rev-parse --short HEAD
        # Current working dir assumed to be repo root or close to it
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], 
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        info["git_head"] = sha
    except Exception:
        info["git_head"] = "Unknown"
        
    return info
