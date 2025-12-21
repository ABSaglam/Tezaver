import json
import hashlib
from pathlib import Path
from typing import Dict, Set, Any, List
from datetime import datetime

class IdempotencyManager:
    """
    MX-5130: Idempotency / Duplicate-order Shield.
    Ensures that for a given signal context, only one order is placed.
    """
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.seen_keys: Set[str] = set()
        self.blocked_count = 0
        self.registry: Dict[str, Dict] = {} # key -> order_meta

    def build_key(self, 
                  symbol: str, 
                  tf: str, 
                  strategy_id: str, 
                  signal_ts: Any, 
                  intent: str, 
                  side: str) -> str:
        """
        Builds a deterministic SHA256 key for a signal context.
        Tr: Sinyal bağlamı için deterministik bir SHA256 anahtarı oluşturur.
        """
        payload = f"{symbol}:{tf}:{strategy_id}:{signal_ts}:{intent}:{side}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def check_and_mark(self, key: str, order_meta: Dict) -> bool:
        """
        Returns True if the key is new (allowed), False if it is a duplicate (blocked).
        Tr: Anahtar yeniyse True, mükerrerse False döner.
        """
        if key in self.seen_keys:
            self.blocked_count += 1
            return False
        
        self.seen_keys.add(key)
        self.registry[key] = {
            "order_id": order_meta.get("order_id"),
            "ts": datetime.now().isoformat(),
            "meta": order_meta
        }
        return True

    def get_summary(self) -> Dict:
        """Returns stats on deduplication."""
        return {
            "run_id": self.run_id,
            "blocked_count": self.blocked_count,
            "unique_orders_count": len(self.seen_keys)
        }

    def save_report(self, report_path: Path):
        """Saves the idempotency registry to disk."""
        report = {
            "run_id": self.run_id,
            "summary": self.get_summary(),
            "keys": self.registry
        }
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
