"""
Tests for Packaging v1
======================

Test ApprovedRallyBundle creation and validation.
"""

import pytest
import pandas as pd
from pathlib import Path
import json
import tempfile
import shutil
from datetime import datetime

from tezaver.sniper.sniper_annotations import SniperAnnotation
from tezaver.foundry.bundle_models import ApprovedRallyBundleManifest
from tezaver.foundry import bundle_io
from tezaver.rally.rally_grade_cards import compute_tier_from_gain_pct


class TestPackagingV1:
    """Test packaging engine."""
    
    def test_manifest_creation(self):
        """Verify manifest can be created and serialized."""
        manifest = ApprovedRallyBundleManifest(
            bundle_id="BTCUSDT_15m_test1",
            symbol="BTCUSDT",
            timeframe="15m",
            event_id="test1",
            event_time_iso="2025-01-01T00:00:00",
            tier="GOLD",
            approved={
                "entry_bar_offset": 5,
                "entry_ts": "2025-01-01T01:15:00"
            },
            qc={
                "verdict": "PASS",
                "score": 80
            }
        )
        
        # Verify serialization
        manifest_dict = manifest.to_dict()
        assert manifest_dict["bundle_version"] == "approved_rally_bundle_v1"
        assert manifest_dict["tier"] == "GOLD"
        assert manifest_dict["approved"]["entry_bar_offset"] == 5
        
        # Verify deserialization
        loaded = ApprovedRallyBundleManifest.from_dict(manifest_dict)
        assert loaded.tier == "GOLD"
        assert loaded.symbol == "BTCUSDT"
    
    def test_bundle_directory_creation(self):
        """Verify bundle directory structure is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_dir = bundle_io.create_bundle_directory(
                "BTCUSDT",
                "15m",
                "test_event_1",
                output_root=tmpdir
            )
            
            assert bundle_dir.exists()
            assert bundle_dir.is_dir()
            assert bundle_dir.name == "test_event_1"
            assert bundle_dir.parent.name == "15m"
            assert bundle_dir.parent.parent.name == "BTCUSDT"
    
    def test_bundle_files_writing(self):
        """Verify all bundle files are written correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_dir = Path(tmpdir) / "BTCUSDT" / "15m" / "test_event"
            bundle_dir.mkdir(parents=True)
            
            manifest = ApprovedRallyBundleManifest(
                bundle_id="BTCUSDT_15m_test",
                symbol="BTCUSDT",
                timeframe="15m",
                event_id="test",
                tier="SILVER"
            )
            
            annotation_dict = {
                "symbol": "BTCUSDT",
                "timeframe": "15m",
                "event_id": "test",
                "entry_bar_offset": 5
            }
            
            qc_report_dict = {
                "qc_verdict": "PASS",
                "score": 75
            }
            
            event_row_dict = {
                "event_id": "test",
                "future_max_gain_pct": 0.15
            }
            
            # Create minimal price window
            price_window_df = pd.DataFrame({
                'open_time': pd.date_range('2025-01-01', periods=10, freq='15T'),
                'open': [100.0] * 10,
                'high': [101.0] * 10,
                'low': [99.0] * 10,
                'close': [100.5] * 10,
                'volume': [1000.0] * 10
            })
            
            # Write bundle files
            written_files = bundle_io.write_bundle_files(
                bundle_dir=bundle_dir,
                manifest=manifest,
                annotation_dict=annotation_dict,
                qc_report_dict=qc_report_dict,
                event_row_dict=event_row_dict,
                price_window_df=price_window_df
            )
            
            # Verify all files exist
            assert (bundle_dir / "manifest.json").exists()
            assert (bundle_dir / "annotation.json").exists()
            assert (bundle_dir / "qc_report.json").exists()
            assert (bundle_dir / "event_row.json").exists()
            assert (bundle_dir / "price_window.parquet").exists()
            
            # Verify manifest contents
            with open(bundle_dir / "manifest.json", 'r') as f:
                loaded_manifest = json.load(f)
                assert loaded_manifest["tier"] == "SILVER"
                assert loaded_manifest["symbol"] == "BTCUSDT"
    
    def test_tier_computation_gold(self):
        """Verify GOLD tier (20%+)."""
        tier = compute_tier_from_gain_pct(0.21)
        assert tier == "GOLD"
    
    def test_tier_computation_diamond(self):
        """Verify DIAMOND tier (30%+)."""
        tier = compute_tier_from_gain_pct(0.35)
        assert tier == "DIAMOND"
    
    def test_tier_computation_silver(self):
        """Verify SILVER tier (10%+)."""
        tier = compute_tier_from_gain_pct(0.12)
        assert tier == "SILVER"
    
    def test_tier_computation_bronze(self):
        """Verify BRONZE tier (5%+)."""
        tier = compute_tier_from_gain_pct(0.07)
        assert tier == "BRONZE"
    
    def test_tier_computation_unknown(self):
        """Verify UNKNOWN tier (<5%)."""
        tier = compute_tier_from_gain_pct(0.03)
        assert tier is None  # Below threshold
    
    def test_price_window_extraction_bounds(self):
        """Verify price window slicing respects bounds."""
        # Create history dataframe
        base_time = pd.Timestamp("2025-01-01 00:00:00")
        history_df = pd.DataFrame({
            'open_time': pd.date_range(base_time, periods=200, freq='15min'),
            'open': [100.0] * 200,
            'high': [101.0] * 200,
            'low': [99.0] * 200,
            'close': [100.5] * 200,
            'volume': [1000.0] * 200
        })
        
        # Event at index 100
        event_time = history_df.iloc[100]['open_time']
        
        # Extract window: [100-50, 100+50] = [50, 150]
        event_idx = 100
        window_before = 50
        window_after = 50
        
        start_idx = max(0, event_idx - window_before)
        end_idx = min(len(history_df), event_idx + window_after + 1)
        
        window = history_df.iloc[start_idx:end_idx]
        
        assert len(window) == window_before + window_after + 1  # 101 bars
        assert window.iloc[0]['open_time'] == history_df.iloc[50]['open_time']
        assert window.iloc[-1]['open_time'] == history_df.iloc[150]['open_time']
