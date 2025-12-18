# Tezaver Bulut - FX Recompute Service
"""
Service to recompute and fill missing FX conversions for past records.
"""

from typing import List, Dict, Any
from datetime import datetime, timezone

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.fx_rate_cache import FxRateCache
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.services.telemetry_ndjson import NdjsonTelemetry

class FxRecomputeService:
    def __init__(self, config: BulutConfig, fx_cache: FxRateCache, persistence: SqlitePersistence, telemetry: NdjsonTelemetry):
        self._config = config
        self._cache = fx_cache
        self._db = persistence
        self._telemetry = telemetry
        
    async def recompute_today_utc(self) -> Dict[str, Any]:
        """
        Scan today's records for missing conversions and fix them.
        Returns summary stats.
        """
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        stats = {
            "income_fixed": 0,
            "audit_fixed": 0,
            "missing_rates": set()
        }
        
        # 1. Income Events
        unconverted_income = self._db.get_unconverted_income(date_str)
        for evt in unconverted_income:
            asset = evt["asset"]
            rate = await self._cache.get_rate(asset)
            
            if rate:
                income = evt["income"]
                usdt_val = income * rate
                source = "RECOMPUTE"
                self._db.update_income_conversion(evt["tran_id"], usdt_val, rate, source)
                stats["income_fixed"] += 1
                
                self._telemetry.emit("FX_CONVERSION_APPLIED", {
                    "kind": "INCOME",
                    "asset": asset,
                    "amount": income,
                    "usdt": usdt_val,
                    "context": "RECOMPUTE"
                })
            else:
                stats["missing_rates"].add(asset)
                
        # 2. Trade Audit
        unconverted_audit = self._db.get_unconverted_audits(date_str)
        for audit in unconverted_audit:
            asset = audit["fee_asset"]
            rate = await self._cache.get_rate(asset)
            
            if rate:
                fee_native = audit["fee_native"]
                # If fee_native is None, maybe we can assume 0? Or skip.
                if fee_native is None:
                    continue
                    
                fee_usdt = fee_native * rate
                
                # We also need to update NET PNL USDT
                # Old Net = Gross - Fee(NULL so 0). 
                # New Net = Gross - Fee(Calculated).
                # Wait, if fee_usdt was NULL, did we subtract it?
                # In upgrade_trade_audit_from_fills: "net_usdt = realized" if asset != USDT.
                # So Gross ~= Realized (for linear futures mostly)
                # Actually gross_pnl_usdt stores realized PnL.
                gross = audit["gross_pnl_usdt"]
                new_net = gross - fee_usdt
                
                source = "RECOMPUTE"
                self._db.update_audit_conversion(audit["id"], fee_usdt, new_net, rate, source)
                stats["audit_fixed"] += 1
                
                self._telemetry.emit("FX_CONVERSION_APPLIED", {
                    "kind": "FEE",
                    "asset": asset,
                    "amount": fee_native,
                    "usdt": fee_usdt,
                    "context": "RECOMPUTE"
                })
            else:
                stats["missing_rates"].add(asset)
                
        # Convert set to list for JSON
        stats["missing_rates"] = list(stats["missing_rates"])
        return stats
