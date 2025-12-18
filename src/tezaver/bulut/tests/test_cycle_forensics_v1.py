import unittest
import json
import sqlite3
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from tezaver.bulut.schemas.cycle_timeline_v1 import CycleTimelineV1, CycleStageV1
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.services.cycle_forensics import CycleForensicsService
from tezaver.bulut.services.incident_bundle import IncidentBundleService
from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.core.config import BulutConfig

class TestCycleForensicsV1(unittest.TestCase):
    
    def setUp(self):
        # Temp dir
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test.db"
        
        # Init persistence
        self.persistence = SqlitePersistence(str(self.db_path))
        
        # Init Service
        self.service = CycleForensicsService()
        
        # Context Mock
        self.ctx = MagicMock(spec=BulutContext)
        self.ctx.persistence = self.persistence
        self.ctx.telemetry = MagicMock()
        self.ctx.config = BulutConfig()
        # Fix config_snapshot mock
        self.ctx.config_snapshot = MagicMock()
        self.ctx.config_snapshot.snapshot_config.return_value = {"mock": "cfg"}
        self.ctx.config_snapshot.hash_config.return_value = "hash"
        
    def tearDown(self):
        # self.persistence.close() # Method does not exist
        shutil.rmtree(self.test_dir)
        
    def test_schema_serialization(self):
        """Verify CycleTimelineV1 builds and dumps correctly."""
        t = CycleTimelineV1(
            cycle_index=1,
            cycle_ts=datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        )
        # Fix positional args: name, status, duration_ms, details
        t.stages.append(CycleStageV1("SCHED", "OK", 0, {"planned": 10}))
        
        d = t.to_dict()
        self.assertEqual(d["cycle_index"], 1)
        self.assertEqual(len(d["stages"]), 1)
        self.assertEqual(d["stages"][0]["name"], "SCHED")
        
        # Round trip
        t2 = CycleTimelineV1.from_dict(d)
        self.assertEqual(t2.cycle_index, 1)
        self.assertEqual(t2.stages[0].details["planned"], 10)
        
    def test_persistence_upsert_and_get(self):
        """Verify saving and retrieving timelines."""
        t_json = json.dumps({"foo": "bar", "cycle_index": 100})
        ts = datetime.now(timezone.utc)
        
        self.persistence.upsert_cycle_timeline(100, ts, t_json)
        
        timelines = self.persistence.get_latest_timelines(limit=5)
        self.assertEqual(len(timelines), 1)
        self.assertEqual(timelines[0]["foo"], "bar")
        self.assertEqual(timelines[0]["cycle_index"], 100)
        
        # Upsert update
        t_json_v2 = json.dumps({"foo": "baz", "cycle_index": 100})
        self.persistence.upsert_cycle_timeline(100, ts, t_json_v2)
        
        timelines = self.persistence.get_latest_timelines(limit=5)
        self.assertEqual(timelines[0]["foo"], "baz")
        
    def test_collector_service(self):
        """Verify service builds correct structure and calls persistence."""
        ts = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
        
        timeline = self.service.collect_and_save(
            self.ctx,
            cycle_index=55,
            cycle_ts=ts,
            sched_stats={"missed_n": 0},
            scan_stats={"candidates_n": 5},
            decider_stats={"final_plans_n": 2},
            exec_stats={"executed_n": 1},
            risk_stats={"halted": False}
        )
        
        self.assertEqual(timeline.cycle_index, 55)
        self.assertEqual(len(timeline.stages), 6) # SCHED, DATA, SCAN, DECIDE, EXEC, RISK
        
        # Verify persistence call
        timelines = self.persistence.get_latest_timelines(1)
        self.assertEqual(len(timelines), 1)
        self.assertEqual(timelines[0]["cycle_index"], 55)
        
        # Verify telemetry
        self.ctx.telemetry.emit.assert_called_with("CYCLE_TIMELINE_SAVED", unittest.mock.ANY)
        
    def test_incident_bundle_integration(self):
        """Verify incident bundle includes timelines.json."""
        # Pre-populate DB
        self.persistence.upsert_cycle_timeline(99, datetime.now(timezone.utc), json.dumps({"id": 99}))
        
        bundle_svc = IncidentBundleService(self.test_dir)
        
        # Mock other components for bundle
        self.ctx.status_service = MagicMock()
        self.ctx.status_service.get_status.return_value = MagicMock(to_dict=lambda: {})
        if hasattr(self.ctx, "config_snapshot"):
            del self.ctx.config_snapshot # Use fallback
            
        # Fix telemetry path mock (prevent shutil.copy on mock)
        if hasattr(self.ctx.telemetry, "_path"):
            del self.ctx.telemetry._path
        
        zip_path = bundle_svc.create_bundle(self.ctx, "test_reason")
        
        # Unzip and check
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as z:
            names = z.namelist()
            # We expect timelines.json inside the bundle folder (which is root/timelines.json inside zip usually? No, bundle_dir struct)
            # The code does: zf.write(abs, rel)
            # rel path should handle it.
            # Usually incident_timestamp_reason/timelines.json
            
            has_timeline = any("timelines.json" in n for n in names)
            self.assertTrue(has_timeline, f"timelines.json not found in {names}")
            
            # Read it
            f_name = next(n for n in names if "timelines.json" in n)
            with z.open(f_name) as f:
                data = json.load(f)
                self.assertEqual(len(data), 1)
                self.assertEqual(data[0]["id"], 99)

if __name__ == "__main__":
    unittest.main()
