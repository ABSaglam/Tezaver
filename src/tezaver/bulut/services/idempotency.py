# Tezaver Bulut - Idempotency Service
"""
Generates deterministic client order IDs.
"""

import hashlib

class IdempotencyService:
    """
    Helper to generate unique client order IDs.
    """
    
    @staticmethod
    def make_client_order_id(key: str) -> str:
        """
        Convert arbitrary uniqueness key to a format suitable for Binance newClientOrderId.
        Binance supports up to 36 chars (alphanumeric, underscores, dashes).
        We use a hash to ensure length and character set compliance.
        """
        # SHA256 hex digest is 64 chars, too long.
        # We can take first 32 chars or encode differently.
        # Or use a prefix + short hash.
        # "tza_" + 20 chars of hash -> 24 chars.
        
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        
        # Taking first 22 chars of hex to be safe and short enough.
        # Prefix "tb_" (Tezaver Bulut)
        return f"tb_{digest[:22]}"
