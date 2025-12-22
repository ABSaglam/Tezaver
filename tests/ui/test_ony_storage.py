"""
Test ONY Storage - SniperAnnotationRepository roundtrip test.

Phase 1 ONY v1 Verification
"""

import pytest
import json
from pathlib import Path

from tezaver.sniper.sniper_annotations import (
    SniperAnnotation,
    SniperAnnotationRepository,
)


def test_sniper_annotation_upsert_roundtrip(tmp_path: Path):
    """
    Test that annotation upsert and load preserves all fields.
    """
    # 1. Create repository with tmp dir
    repo = SniperAnnotationRepository(base_dir=tmp_path)
    
    # 2. Create and upsert an annotation
    symbol = "BTCUSDT"
    timeframe = "15m"
    event_id = "test_event_123"
    
    ann = repo.append(
        symbol=symbol,
        timeframe=timeframe,
        event_id=event_id,
        entry_bar_offset=10,
        exit_bar_offset=40,
        note="Test annotation",
        status="PENDING",
        label="GOOD",
    )
    
    # 3. Verify file was created
    expected_path = tmp_path / symbol / timeframe / "sniper_annotations_v1.json"
    assert expected_path.exists(), f"Annotation file not created at {expected_path}"
    
    # 4. Load and verify fields
    loaded = repo.get_one(symbol, timeframe, event_id)
    
    assert loaded is not None, "Annotation not found after upsert"
    assert loaded.symbol == symbol
    assert loaded.timeframe == timeframe
    assert loaded.event_id == event_id
    assert loaded.entry_bar_offset == 10
    assert loaded.exit_bar_offset == 40
    assert loaded.note == "Test annotation"
    assert loaded.status == "PENDING"
    assert loaded.label == "GOOD"
    
    # 5. Update status to APPROVED
    ann2 = repo.append(
        symbol=symbol,
        timeframe=timeframe,
        event_id=event_id,
        entry_bar_offset=10,
        exit_bar_offset=40,
        note="Test annotation",
        status="APPROVED",
        label="GOOD",
    )
    
    # 6. Verify update
    loaded2 = repo.get_one(symbol, timeframe, event_id)
    assert loaded2.status == "APPROVED", "Status not updated to APPROVED"


def test_sniper_annotation_list_by_status(tmp_path: Path):
    """
    Test filtering annotations by status.
    """
    repo = SniperAnnotationRepository(base_dir=tmp_path)
    symbol = "ETHUSDT"
    timeframe = "1h"
    
    # Create multiple annotations with different statuses
    repo.append(symbol, timeframe, "event_1", 5, status="PENDING")
    repo.append(symbol, timeframe, "event_2", 10, status="APPROVED")
    repo.append(symbol, timeframe, "event_3", 15, status="APPROVED")
    repo.append(symbol, timeframe, "event_4", 20, status="REJECTED")
    
    # Filter by status
    pending = repo.list_by_status(symbol, timeframe, "PENDING")
    approved = repo.list_by_status(symbol, timeframe, "APPROVED")
    rejected = repo.list_by_status(symbol, timeframe, "REJECTED")
    
    assert len(pending) == 1
    assert len(approved) == 2
    assert len(rejected) == 1
    
    assert pending[0].event_id == "event_1"
    assert rejected[0].event_id == "event_4"


def test_sniper_annotation_json_roundtrip(tmp_path: Path):
    """
    Test that JSON file is readable and valid.
    """
    repo = SniperAnnotationRepository(base_dir=tmp_path)
    symbol = "SOLUSDT"
    timeframe = "4h"
    
    repo.append(symbol, timeframe, "json_test", 7, note="JSON test")
    
    # Read raw JSON
    json_path = tmp_path / symbol / timeframe / "sniper_annotations_v1.json"
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["event_id"] == "json_test"
    assert data[0]["entry_bar_offset"] == 7
