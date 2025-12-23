"""
Tests for Foundry Bundle Scanning
==================================

Test bundle inventory scanning and filtering.
"""

import pytest
import tempfile
import json
from pathlib import Path
import pandas as pd

from tezaver.foundry.bundle_index import scan_bundles, filter_bundles


class TestFoundryBundleScan:
    """Test bundle scanning logic."""
    
    def test_scan_empty_directory(self):
        """Scan should return empty DataFrame if no bundles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            df = scan_bundles(tmpdir)
            assert df.empty
    
    def test_scan_single_bundle(self):
        """Scan should detect a single bundle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create bundle structure
            bundle_dir = Path(tmpdir) / "BTCUSDT" / "15m" / "test_event_1"
            bundle_dir.mkdir(parents=True)
            
            # Create manifest
            manifest = {
                "bundle_version": "approved_rally_bundle_v1",
                "bundle_id": "BTCUSDT_15m_test1",
                "symbol": "BTCUSDT",
                "timeframe": "15m",
                "event_id": "test_event_1",
                "tier": "GOLD",
                "event_time_iso": "2025-01-01T00:00:00",
                "approved": {
                    "entry_ts": "2025-01-01T01:00:00",
                    "exit_ts": "2025-01-01T05:00:00"
                },
                "qc": {
                    "verdict": "PASS",
                    "score": 85
                }
            }
            
            with open(bundle_dir / "manifest.json", 'w') as f:
                json.dump(manifest, f)
            
            # Scan
            df = scan_bundles(tmpdir)
            
            # Assertions
            assert len(df) == 1
            assert df.iloc[0]["symbol"] == "BTCUSDT"
            assert df.iloc[0]["timeframe"] == "15m"
            assert df.iloc[0]["tier"] == "GOLD"
            assert df.iloc[0]["qc_verdict"] == "PASS"
            assert df.iloc[0]["qc_score"] == 85
    
    def test_scan_multiple_bundles(self):
        """Scan should detect multiple bundles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 3 bundles
            for i in range(3):
                bundle_dir = Path(tmpdir) / "BTCUSDT" / "15m" / f"event_{i}"
                bundle_dir.mkdir(parents=True)
                
                manifest = {
                    "symbol": "BTCUSDT",
                    "timeframe": "15m",
                    "event_id": f"event_{i}",
                    "tier": ["GOLD", "SILVER", "BRONZE"][i],
                    "event_time_iso": f"2025-01-0{i+1}T00:00:00",
                    "qc": {"verdict": "PASS", "score": 80 - i*10}
                }
                
                with open(bundle_dir / "manifest.json", 'w') as f:
                    json.dump(manifest, f)
            
            df = scan_bundles(tmpdir)
            
            assert len(df) == 3
            # Check sorted by qc_score desc
            assert df.iloc[0]["qc_score"] == 80  # Highest score first
    
    def test_filter_by_symbol(self):
        """Filter should work for symbol."""
        df = pd.DataFrame([
            {"symbol": "BTCUSDT", "timeframe": "15m", "tier": "GOLD", "qc_verdict": "PASS", "qc_score": 80},
            {"symbol": "ETHUSDT", "timeframe": "1h", "tier": "SILVER", "qc_verdict": "PASS", "qc_score": 75}
        ])
        
        filtered = filter_bundles(df, symbol="BTCUSDT")
        
        assert len(filtered) == 1
        assert filtered.iloc[0]["symbol"] == "BTCUSDT"
    
    def test_filter_by_tier(self):
        """Filter should work for tier."""
        df = pd.DataFrame([
            {"symbol": "BTCUSDT", "timeframe": "15m", "tier": "GOLD", "qc_verdict": "PASS", "qc_score": 80},
            {"symbol": "ETHUSDT", "timeframe": "1h", "tier": "SILVER", "qc_verdict": "PASS", "qc_score": 75},
            {"symbol": "SOLUSDT", "timeframe": "4h", "tier": "DIAMOND", "qc_verdict": "PASS", "qc_score": 90}
        ])
        
        filtered = filter_bundles(df, tiers=["GOLD", "DIAMOND"])
        
        assert len(filtered) == 2
        assert "SILVER" not in filtered["tier"].values
    
    def test_filter_by_min_qc_score(self):
        """Filter should work for min QC score."""
        df = pd.DataFrame([
            {"symbol": "BTCUSDT", "timeframe": "15m", "tier": "GOLD", "qc_verdict": "PASS", "qc_score": 80},
            {"symbol": "ETHUSDT", "timeframe": "1h", "tier": "SILVER", "qc_verdict": "PASS", "qc_score": 60},
            {"symbol": "SOLUSDT", "timeframe": "4h", "tier": "BRONZE", "qc_verdict": "PASS", "qc_score": 50}
        ])
        
        filtered = filter_bundles(df, min_qc_score=70)
        
        assert len(filtered) == 1
        assert filtered.iloc[0]["qc_score"] == 80
    
    def test_filter_combined(self):
        """Combined filters should work together."""
        df = pd.DataFrame([
            {"symbol": "BTCUSDT", "timeframe": "15m", "tier": "GOLD", "qc_verdict": "PASS", "qc_score": 80},
            {"symbol": "BTCUSDT", "timeframe": "1h", "tier": "SILVER", "qc_verdict": "PASS", "qc_score": 70},
            {"symbol": "ETHUSDT", "timeframe": "15m", "tier": "GOLD", "qc_verdict": "FAIL", "qc_score": 40}
        ])
        
        filtered = filter_bundles(
            df,
            symbol="BTCUSDT",
            timeframe="15m",
            tiers=["GOLD"],
            qc_verdicts=["PASS"],
            min_qc_score=60
        )
        
        assert len(filtered) == 1
        assert filtered.iloc[0]["symbol"] == "BTCUSDT"
        assert filtered.iloc[0]["timeframe"] == "15m"
        assert filtered.iloc[0]["tier"] == "GOLD"
