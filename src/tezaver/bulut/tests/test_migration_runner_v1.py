import pytest
from unittest.mock import MagicMock
from tezaver.bulut.services.migration_runner import MigrationRunner
from tezaver.bulut.migrations import v001_initial_schema, v002_add_trade_audit

# Mock persistence
class MockPersistence:
    def __init__(self, ver=0):
        self._ver = ver
        self._conn = MagicMock()
        self._cursor = MagicMock()
        self._conn.cursor.return_value = self._cursor
        
    def get_schema_version(self):
        return self._ver
        
    def _get_conn(self):
        return self._conn

def test_migration_runner_applies_in_order():
    p = MockPersistence(ver=0)
    runner = MigrationRunner(p)
    
    # Mock discovery to return only 2 known migrations for testing
    runner._discover_migrations = MagicMock(return_value=[v001_initial_schema, v002_add_trade_audit])
    
    # Run
    report = runner.run_pending(dry_run=False)
    
    assert len(report["executed"]) == 2
    assert report["executed"] == [1, 2]
    
    # Verify SQL calls
    # v1 applied
    # v2 applied
    # schema_version updated twice
    assert p._cursor.execute.call_count >= 2 # At least schema updates + migration SQLs
    
    # Verify schema version update calls
    calls = p._cursor.execute.call_args_list
    # Search for schema_meta updates
    meta_updates = [c for c in calls if "INSERT INTO schema_meta" in c[0][0]]
    assert len(meta_updates) == 2

def test_dry_run_lists_sql():
    p = MockPersistence(ver=0)
    runner = MigrationRunner(p)
    runner._discover_migrations = MagicMock(return_value=[v001_initial_schema])
    
    report = runner.run_pending(dry_run=True)
    
    assert "plan" in report
    assert len(report["plan"]) == 1
    assert report["plan"][0]["version"] == 1
    assert "positions" in report["plan"][0]["sql"][0] # Check content
    
    # Verify NO execution
    p._cursor.execute.assert_not_called()

def test_idempotent_no_run_if_updated():
    p = MockPersistence(ver=2) # Already at v2
    runner = MigrationRunner(p)
    runner._discover_migrations = MagicMock(return_value=[v001_initial_schema, v002_add_trade_audit])
    
    report = runner.run_pending(dry_run=False)
    
    assert len(report["executed"]) == 0
    p._cursor.execute.assert_not_called()
