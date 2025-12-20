import os
import pytest
import time
from tezaver.matrix.core.cloud_loop import CloudLoopSupervisor

def test_cloud_loop_lock_prevents_concurrent(tmp_path):
    home = str(tmp_path)
    sup1 = CloudLoopSupervisor(home)
    sup2 = CloudLoopSupervisor(home)
    
    # Acquire lock 1 manually
    assert sup1.acquire_lock() is True
    
    # Try acquire lock 2
    assert sup2.acquire_lock() is False
    
    # Release 1
    sup1.release_lock()
    
    # Acquire 2
    assert sup2.acquire_lock() is True
    sup2.release_lock()
