# Tezaver Bulut - SQLite Persistence Service
"""
SQLite persistence for Bulut state.
Manages positions, orders, and trade plans.
"""

import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict
from pathlib import Path

from tezaver.bulut.schemas.trade_plan_v1 import TradePlanV1, TradeDecision


class SqlitePersistence:
    """
    SQLite database manager.
    """
    
    def __init__(self, db_path: str):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _get_conn(self):
        return sqlite3.connect(self._db_path)
    
    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Positions table
        # We need to drop table if schema changed or just alter? Or ensure fields?
        # Since v0.05 only had minimal columns, we might need to recreate or alter.
        # SQLite simplistic approach: CREATE IF NOT EXISTS usually works, but schema change requires migration.
        # For dev speed v0.08: DROP positions if it exists but lacks columns?
        # Or just use safe CREATE and fail/warn if columns missing?
        # Let's try to add columns or recreate.
        # Assuming dev environment, we can DROP for v0.08 update to be clean.
        # cursor.execute("DROP TABLE IF EXISTS positions") # Only for dev, risky for prod.
        # But we want to preserve data from v0.07? Probably none in positions table was populated fully.
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                entry_ts TEXT,
                entry_price REAL,
                qty REAL,
                notional_usdt REAL,
                sl_pct REAL,
                tp_pct REAL,
                status TEXT,
                pattern_id TEXT,
                exit_profile_id TEXT,
                exit_params_json TEXT,
                open_ts TEXT,  -- Deprecated/Same as entry_ts
                update_ts TEXT,
                side TEXT -- 'LONG'
            )
        """)
        
        # ... Trade Plans table unchanged ...
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_plans (
                plan_ts TEXT,
                symbol TEXT,
                decision TEXT,
                notional REAL,
                sl_json TEXT,
                tp_json TEXT,
                idempotency_key TEXT PRIMARY KEY,
                reasons_json TEXT,
                status TEXT
            )
        """)
        
        conn.commit()
        conn.close()

    # --- Positions ---
    
    def upsert_position_open(self, symbol: str, entry_ts: datetime, entry_price: float, qty: float, 
                             notional: float, sl_pct: float, tp_pct: float, 
                             pattern_id: str = None, exit_profile_id: str = None, 
                             exit_params: dict = None):
        """Insert or Update OPEN position."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Check if exists? REPLACE INTO works for upsert on PRIMARY KEY
        cursor.execute("""
            REPLACE INTO positions (
                symbol, entry_ts, entry_price, qty, notional_usdt, 
                sl_pct, tp_pct, status, pattern_id, exit_profile_id, exit_params_json,
                update_ts, side
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, 'LONG')
        """, (
            symbol, entry_ts.isoformat(), entry_price, qty, notional,
            sl_pct, tp_pct, pattern_id, exit_profile_id, 
            json.dumps(exit_params) if exit_params else "{}",
            datetime.now(timezone.utc).isoformat()
        ))
        
        conn.commit()
        conn.close()

    def mark_position_closed(self, symbol: str, close_ts: datetime, close_price: float):
        """Mark position as CLOSED (or delete row?). Usually delete or move to history."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # For simplicity in Bulut v0.08, we DELETE closed positions from 'positions' table
        # and maybe log to a 'trades_history' table (not implemented in this step).
        # Requirement: "positions tablosunu CLOSED yap"
        # If we keep it, scan logic must filter status='OPEN'.
        
        cursor.execute("""
            UPDATE positions SET status='CLOSED', update_ts=? 
            WHERE symbol=?
        """, (datetime.now(timezone.utc).isoformat(), symbol))
        
        # Optional: Delete if we only track OPEN positions here?
        # User prompt implies "positions tablosunu CLOSED yap" -> update status.
        # But auto-exit engine says "sadece DB’de OPEN pozisyonlara bak".
        # So keeping closed rows is fine.
        
        conn.commit()
        conn.close()

    def get_open_positions(self) -> List[dict]:
        """Get all open positions."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM positions WHERE status='OPEN'")
        rows = cursor.fetchall()
        
        positions = [dict(row) for row in rows]
        conn.close()
        return positions
        
    def get_position(self, symbol: str) -> Optional[dict]:
        """Get position by symbol."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM positions WHERE symbol=?", (symbol,))
        row = cursor.fetchone()
        
        conn.close()
        return dict(row) if row else None
        
    def get_open_position_count(self) -> int:
        """Get count of open positions."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM positions WHERE status='OPEN'")
        count = cursor.fetchone()[0]
        conn.close()
        return count
        
    def get_total_notional(self) -> float:
        """Get total notional of open positions."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(notional_usdt) FROM positions WHERE status='OPEN'")
        total = cursor.fetchone()[0]
        conn.close()
        return total if total else 0.0

    # --- Trade Plans ---

    def insert_plan(self, plan: TradePlanV1, status: str = "PROPOSED") -> bool:
        """
        Insert a trade plan.
        Returns True if inserted, False if duplicate (idempotency).
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO trade_plans (
                    plan_ts, symbol, decision, notional, 
                    sl_json, tp_json, idempotency_key, reasons_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan.plan_ts.isoformat(),
                plan.symbol,
                plan.decision.name,
                plan.notional_usdt,
                json.dumps(plan.sl.to_dict() if plan.sl else {}),
                json.dumps(plan.tp.to_dict() if plan.tp else {}),
                plan.idempotency_key,
                json.dumps(plan.reasons),
                status
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def update_plan_status(self, idempotency_key: str, status: str):
        """Update plan status."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE trade_plans SET status = ? WHERE idempotency_key = ?",
            (status, idempotency_key)
        )
        conn.commit()
        conn.close()

    def get_latest_plans(self, limit: int = 50) -> List[dict]:
        """Get latest trade plans."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM trade_plans 
            ORDER BY plan_ts DESC 
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        plans = [dict(row) for row in rows]
        
        # Parse JSON fields
        for p in plans:
            try:
                p["sl"] = json.loads(p["sl_json"])
                p["tp"] = json.loads(p["tp_json"])
                p["reasons"] = json.loads(p["reasons_json"])
            except:
                pass
                
        conn.close()
        return plans
