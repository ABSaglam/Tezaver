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
    def make_client_order_id(key: str, prefix: str = "tb_", max_len: int = 36) -> str:
        """
        Convert arbitrary uniqueness key to a format suitable for Binance newClientOrderId.
        """
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        
        # Calculate available length for hash
        # prefix length + hash length <= max_len
        # We need as much hash as possible.
        
        limit = max_len - len(prefix)
        if limit < 8:
            # Fallback if prefix assumes too much space
            limit = 8
            
        return f"{prefix}{digest[:limit]}"
