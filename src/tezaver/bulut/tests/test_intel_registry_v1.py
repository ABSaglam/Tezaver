import unittest
import shutil
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from tezaver.bulut.core.context import BulutContext, BulutConfig
from tezaver.bulut.schemas.intel_bundle_v1 import IntelBundleV1, IntelArtifactV1
from tezaver.bulut.services.intel_registry import IntelRegistryService
from tezaver.bulut.services.pattern_pack_loader import PatternPackLoader

class TestIntelRegistryV1(unittest.TestCase):
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.root = Path(self.test_dir)
        self.intel_root = self.root / "bulut_intel"
        self.registry = IntelRegistryService(self.root)
        
        self.ctx = MagicMock(spec=BulutContext)
        self.ctx.config = BulutConfig()
        self.ctx.state = MagicMock()
        self.ctx.state.execution_armed = False
        self.ctx.telemetry = MagicMock()
        self.ctx.pattern_loader = MagicMock()
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        
    def _create_incoming_bundle(self, bundle_id: str) -> Path:
        """Helper to create a valid incoming bundle."""
        path = self.intel_root / "incoming" / bundle_id
        path.mkdir(parents=True, exist_ok=True)
        
        # Create dummy artifacts
        art1 = path / "pattern_pack.json"
        with open(art1, "w") as f: json.dump({"pack_id": "test_pack", "hash": "abc"}, f)
        
        # Create meta
        bundle = IntelBundleV1(
            bundle_id=bundle_id,
            bundle_hash="hash_of_content"
        )
        bundle.artifacts.append(IntelArtifactV1(name="pattern_pack.json", path="pattern_pack.json", sha256="abc"))
        
        with open(path / "intel_bundle.json", "w") as f:
            json.dump(bundle.to_dict(), f)
            
        return path

    def test_lifecycle_publish_activate(self):
        """Verify: Incoming -> Published -> Active Pointer."""
        bid = "20250101_test"
        self._create_incoming_bundle(bid)
        
        # 1. Publish
        self.registry.publish(self.ctx, bid)
        
        self.assertTrue((self.intel_root / "published" / bid / "intel_bundle.json").exists())
        self.ctx.telemetry.emit.assert_called_with("INTEL_PUBLISHED", {"bundle_id": bid})
        
        # 2. Activate
        self.registry.activate(self.ctx, bid)
        
        ptr = self.registry.get_active()
        self.assertIsNotNone(ptr)
        self.assertEqual(ptr["bundle_id"], bid)
        self.assertEqual(ptr["hash"], "hash_of_content") # from bundle meta
        
        # Hot Reload triggered
        self.ctx.pattern_loader.check_reload.assert_called_with(force=True)

    def test_mainnet_safety_lock(self):
        """Verify: Block publish/activate when on Mainnet+Armed."""
        # 1. Set environment
        # Use patch because dataclass is frozen if we use real
        # Or just mock the config object attr
        self.ctx.config = MagicMock()
        self.ctx.config.mode = "REAL_MAINNET"
        self.ctx.config.intel_edit_block_on_mainnet_armed = True
        self.ctx.state.execution_armed = True
        
        bid = "20250101_prod"
        self._create_incoming_bundle(bid)
        
        # Publish should fail
        with self.assertRaisesRegex(RuntimeError, "INTEL_CHANGE_BLOCKED"):
            self.registry.publish(self.ctx, bid)
            
        # Unarm -> Should work
        self.ctx.state.execution_armed = False
        self.registry.publish(self.ctx, bid) # OK
        
    def test_pattern_pack_loader_integration(self):
        """
        Verify real PatternPackLoader reads active_pointer.json correctly.
        """
        # Create registry structure
        bid = "loader_test"
        self._create_incoming_bundle(bid)
        self.registry.publish(self.ctx, bid)
        self.registry.activate(self.ctx, bid)
        
        ptr_path = self.intel_root / "active_pointer.json"
        
        # Init loader with pointer path
        loader = PatternPackLoader(str(self.root / "legacy_inbox"), active_pointer_path=ptr_path)
        
        # Create VALID pattern pack content to ensure success
        from tezaver.bulut.schemas.pattern_pack_v1 import PatternPackV1
        valid_json = PatternPackV1(
            pack_id="real_pack", 
            hash="123",
            built_at=datetime.now(timezone.utc),
            symbols=["BTCUSDT"],
            timeframes=["15m"]
        ).to_dict()
        
        # Overwrite the file in published
        target = self.intel_root / "published" / bid / "pattern_pack.json"
        with open(target, "w") as f: json.dump(valid_json, f)
        
        # Reload
        reloaded = loader.check_reload()
        
        self.assertTrue(reloaded)
        self.assertIsNotNone(loader._cached_pack)
        self.assertEqual(loader._cached_pack.pack_id, "real_pack")
        
        # Verify it loaded from PUBLISHED dir not legacy
        self.assertTrue(str(target) in str(loader._cached_path))

if __name__ == "__main__":
    unittest.main()
