"""
ONY Auto-Approver Daemon
========================

Scans rally store (Unified SQLite) and automatically creates 
APPROVED annotations for any event that doesn't have one.

Philosophy: "Default Approve" - Trust the scanner.
"""

import pandas as pd
from typing import List, Optional
import logging
from tezaver.core.rally_store import RallyStore
from tezaver.core.annotations import SniperStatus

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OnyAutoApprover")


class OnyAutoApprover:
    def __init__(self):
        self.store = RallyStore()

    def process_symbol(self, symbol: str, timeframe: str) -> int:
        """
        Scan events in Store for symbol/tf and auto-approve.
        Returns count of touched (created/updated) annotations.
        """
        # 1. Fetch All Rallies from Store
        rallies = self.store.list_rallies(symbol=symbol, timeframe=timeframe)
        if not rallies:
            return 0
        
        count = 0
        
        for r in rallies:
            eid = r['id']
            rev = r.get('rev_data', {}) or {}
            
            # Check Status
            curr_status = rev.get('status')
            
            # If no status (New) or PENDING -> Approve
            if not curr_status or curr_status == SniperStatus.PENDING:
                rev.update({
                    'status': SniperStatus.APPROVED,
                    'label': rev.get('label', 'GOOD'),
                    'note': (rev.get('note', '') + " [Auto-Approved]").strip(),
                    'updated_at': pd.Timestamp.now()
                })
                
                # Upsert
                self.store.upsert_rally(eid, rev, layer='rev')
                count += 1
                
        if count > 0:
            logger.info(f"[{symbol} {timeframe}] Auto-Approved {count} events.")
            
        return count

    def scan_all_coins(self):
        """Scan all coins present in store logic?"""
        # We can iterate symbols known in store, or rely on caller to pass symbols.
        # This method is rarely called standalone, usually per symbol.
        pass

if __name__ == "__main__":
    # Standalone run?
    pass
