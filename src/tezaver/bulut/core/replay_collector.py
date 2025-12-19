# Tezaver Bulut - Replay Collector Service
"""
Service to snapshot current or historical state into a Replay Bundle.
"""
import json
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional

from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.schemas.replay_v1 import ReplayBundleV1, ReplayBarV1

class ReplayCollectorService:
    def __init__(self, context: BulutContext):
        self.context = context
        
    def create_bundle_from_current_state(self, notes: str = "") -> ReplayBundleV1:
        """
        Snapshot CURRENT state (Bars, Config, Policy, etc.) into a bundle.
        This captures the "now" for future replay.
        """
        now_ts = datetime.now(timezone.utc).isoformat()
        bundle_id = str(uuid.uuid4())
        
        # 1. Bars Snapshot
        # Grab from 15m store (in-memory cache)
        # We need to serialize them.
        bars_snap = self._snapshot_active_bars()
        
        # 2. Policy State
        # Fetch from DB logic or memory? Context has `policy` engine 
        # but state is in DB `policy_states`. reading from DB is safer.
        policy_snap = self._snapshot_policy_state()
        
        # 3. Config
        # Active config
        cfg_json = json.dumps(self.context.config.to_dict())
        cfg_hash = hashlib.sha256(cfg_json.encode()).hexdigest()
        
        # 4. Risk / Limits
        # Snapshot group caps / open positions summary
        risk_snap = self._snapshot_risk_state()
        
        # 5. Universe
        # Currently active universe
        universe = self.context.universe_source.get_active_universe()
        
        # 6. Expected Outputs
        # Since we are capturing "now" BEFORE execution (or just random time), 
        # we might not know expected outputs unless we just ran a cycle.
        # Ideally, we call this AFTER a cycle finishes, passing the results.
        # But for now, let's leave expected empty or let caller populate.
        
        bundle = ReplayBundleV1(
            bundle_id=bundle_id,
            cycle_ts=now_ts, # Approximate
            created_ts=now_ts,
            universe=universe,
            bars_snapshot=bars_snap,
            policy_state=policy_snap,
            active_config_hash=cfg_hash,
            active_config_json=cfg_json,
            risk_state_json=json.dumps(risk_snap),
            expected_decision_ids={},
            expected_plans={},
            notes=notes
        )
        
        self._save_bundle(bundle)
        return bundle

    def _snapshot_active_bars(self) -> Dict[str, Dict[str, List[dict]]]:
        """Snapshot current bars from memory store."""
        snap = {}
        # Iterate all symbols in store? Or just universe?
        # Store doesn't expose iterator easily maybe. 
        # Let's use universe.
        universe = self.context.universe_source.get_active_universe()
        store = self.context.bars_store
        
        for symbol in universe:
            # Get 15m vars
            bars = store.get_bars(symbol, "15m", limit=500) # Capture context
            if bars:
                # Convert to dicts
                bar_list = []
                for b in bars:
                    # b is Bar(ts, o, h, l, c, v)
                    # We convert to dict
                    bar_list.append({
                        "ts": b.ts, 
                        "o": b.o, "h": b.h, "l": b.l, "c": b.c, "v": b.v
                    })
                if symbol not in snap: snap[symbol] = {}
                snap[symbol]["15m"] = bar_list
        return snap

    def _snapshot_policy_state(self) -> Dict[str, dict]:
        """Snapshot policy states from DB."""
        # We can scan all table?
        conn = self.context.persistence._get_conn()
        conn.row_factory = self._dict_factory
        cur = conn.cursor()
        cur.execute("SELECT * FROM policy_states")
        rows = cur.fetchall()
        conn.close()
        
        return {r["symbol"]: r for r in rows}

    def _snapshot_risk_state(self) -> dict:
        """Snapshot internal risk counters."""
        return {
            "open_positions": self.context.persistence.get_open_position_count(),
            "total_notional": self.context.persistence.get_total_notional(),
            # Daily stats from PortfolioRisk service if exposed
            # For now just basic stats
        }

    def _save_bundle(self, bundle: ReplayBundleV1):
        """Persist bundle to DB."""
        payload = json.dumps(bundle.to_dict())
        conn = self.context.persistence._get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO replay_bundles (bundle_id, cycle_ts, created_ts, payload_json, status, notes)
            VALUES (?, ?, ?, ?, 'CREATED', ?)
        """, (bundle.bundle_id, bundle.cycle_ts, bundle.created_ts, payload, bundle.notes))
        conn.commit()
        conn.close()

    def _dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d
    
    def get_bundle(self, bundle_id: str) -> Optional[ReplayBundleV1]:
        """Load bundle from DB."""
        conn = self.context.persistence._get_conn()
        conn.row_factory = self._dict_factory
        cur = conn.cursor()
        cur.execute("SELECT payload_json FROM replay_bundles WHERE bundle_id=?", (bundle_id,))
        row = cur.fetchone()
        conn.close()
        
        if not row:
            return None
            
        data = json.loads(row["payload_json"])
        
        # Reconstruct
        # bars_snapshot needs just dicts
        # ReplayBundleV1 is dataclass
        # We can construct strictly or assume dict unpacking works if simple types
        # ReplayBundleV1 fields match json keys mostly
        
        return ReplayBundleV1(
            bundle_id=data["bundle_id"],
            cycle_ts=data["cycle_ts"],
            created_ts=data["created_ts"],
            universe=data["universe"],
            bars_snapshot=data["bars_snapshot"],
            policy_state=data["policy_state"],
            active_config_hash=data["active_config_hash"],
            active_config_json=data["active_config_json"],
            risk_state_json=data["risk_state_json"],
            expected_decision_ids=data.get("expected_decision_ids", {}),
            expected_plans=data.get("expected_plans", {}),
            notes=data.get("notes", "")
        )
