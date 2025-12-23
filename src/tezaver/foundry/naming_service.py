"""
Foundry Bundle Naming Service
=============================

Auto-generates standardized Bundle IDs for new Foundry production.
Format: [SYMBOL]-[TIMEFRAME]-[TIER]-[SEQ]
Example: BTC-15m-GOLD-01

Features:
- Scans existing bundles to determine next sequence number.
- Supports special type overrides (e.g., HCM).
"""

import re
import pandas as pd
from typing import Optional
from tezaver.foundry.bundle_index import scan_bundles

class BundleNamingService:
    def __init__(self, bundles_root: str = ".tezaver_matrix/approved_bundles_v1"):
        self.bundles_root = bundles_root
        
    def generate_id(self, symbol: str, timeframe: str, tier: str, special_tag: str = None) -> str:
        """
        Generates the next available Bundle ID.
        
        Args:
            symbol (str): e.g. "BTC" or "BTCUSDT" (will be normalized to symbol root usually, or kept as is)
            timeframe (str): e.g. "15m"
            tier (str): e.g. "GOLD"
            special_tag (str): Optional override for Tier/Type, e.g. "HCM". 
                               If provided, it replaces Tier in the naming schema.
        
        Returns:
            str: The new Bundle ID, e.g. "BTC-15m-GOLD-02"
        """
        # 1. Normalize Components
        # We usually want "BTC" not "BTCUSDT" in concise IDs, but user asked for "Coin Adı".
        # Let's keep it simple: Use input as is, but maybe strip USDT if it's too long? 
        # User example: "BTC-15m-GOLD-01".
        
        # Clean symbol: "BTCUSDT" -> "BTC" if typically used, or just use what is passed.
        # Let's assume the user passes "BTC". If they pass "BTCUSDT", we might want to trim.
        # For now, we trust the input `symbol` is what they want in the ID.
        
        clean_symbol = symbol.replace("USDT", "").replace("usdt", "").upper()
        clean_tf = timeframe.lower()
        
        # Determine the 'Class' segment (Tier or Special Tag)
        class_segment = special_tag.upper() if special_tag else tier.upper()
        
        base_prefix = f"{clean_symbol}-{clean_tf}-{class_segment}"
        
        # 2. Find next sequence
        next_seq = self._get_next_sequence_number(base_prefix)
        
        # 3. Formulate ID
        return f"{base_prefix}-{next_seq:02d}"

    def _get_next_sequence_number(self, prefix: str) -> int:
        """Scans existing bundles to find the max sequence for this prefix."""
        df = scan_bundles(self.bundles_root)
        
        if df.empty or "bundle_id" not in df.columns:
            return 1
            
        # Filter for IDs starting with prefix
        # We look for "{prefix}-" to ensure we match "BTC-15m-GOLD-" and not "BTC-15m-GOLDEN-"
        target_pattern = f"^{re.escape(prefix)}-(\\d+)$"
        
        max_seq = 0
        
        for bid in df["bundle_id"]:
            match = re.match(target_pattern, str(bid))
            if match:
                seq = int(match.group(1))
                if seq > max_seq:
                    max_seq = seq
                    
        return max_seq + 1
