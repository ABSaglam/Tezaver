import os
import json
import pytest
import subprocess
from tezaver.matrix.core.golden_e2e import run_golden_e2e

def test_golden_e2e_core(tmp_path):
    home = str(tmp_path)
    
    # Run Core
    res = run_golden_e2e(home)
    
    # Assert IDs
    assert res["ids"]["candidate_id"] == "AVAX_15m_v4_2099_01_01T00_00_00"
    assert res["ids"]["strategy_id"].startswith("STRAT_")
    
    # Assert Artifacts
    # Approved
    app_dir = tmp_path / "approved" / res["ids"]["candidate_id"]
    assert app_dir.exists()
    
    # Export
    exp_dir = tmp_path / "exports" / res["ids"]["export_dir"]
    assert exp_dir.exists()
    
    # Cloud Strategy
    strat_dir = tmp_path / "cloud_registry" / "strategies" / res["ids"]["strategy_id"]
    assert strat_dir.exists()
    
    # Ops Reports
    assert (tmp_path / "ops" / "preflight" / "latest.json").exists()
    assert (tmp_path / "ops" / "recovery" / "latest.json").exists()
    
    # E2E Bundle
    e2e_dir = tmp_path / "e2e" / res["e2e_id"]
    assert e2e_dir.exists()
    assert (e2e_dir / "manifest.json").exists()
    assert (e2e_dir / "links.json").exists()
    assert (e2e_dir / "inputs" / "candidate.json").exists()
