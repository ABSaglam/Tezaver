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
                side TEXT, -- 'LONG'
                sl_order_id TEXT,
                tp_order_id TEXT,
                sl_client_order_id TEXT,
                tp_client_order_id TEXT,
                protective_status TEXT -- NONE|PLACED|CANCELLED|FAILED
            )
        """)
        
        # Check if columns exit (migration hack for dev)
        # If we just add them to create if not exists, it won't add to existing table.
        # We can try ALTER TABLE safely.
        try:
            cursor.execute("ALTER TABLE positions ADD COLUMN sl_order_id TEXT")
            cursor.execute("ALTER TABLE positions ADD COLUMN tp_order_id TEXT")
            cursor.execute("ALTER TABLE positions ADD COLUMN sl_client_order_id TEXT")
            cursor.execute("ALTER TABLE positions ADD COLUMN tp_client_order_id TEXT")
            cursor.execute("ALTER TABLE positions ADD COLUMN protective_status TEXT")
        except:
            pass # Already exists or table created new with full schema?
            # Actually standard Create if not exists with new schema won't update exist.
            # But the Create statement above DOES NOT HAVE the new columns if I'm editing it.
            # I must ensure the CREATE statement has them for new tables.
            # And ALTER for existing.
        
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
        
        # Schema updates for v0.12 (Risk)
        try:
            cursor.execute("CREATE TABLE IF NOT EXISTS trade_audit (symbol TEXT, close_ts TEXT, pnl REAL, exit_reason TEXT, notional REAL)")
            cursor.execute("ALTER TABLE positions ADD COLUMN last_exit_reason TEXT")
            cursor.execute("ALTER TABLE positions ADD COLUMN last_exit_ts TEXT")
        except:
             pass

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
        # For v0.12, we want to preserve last_exit info if updating same symbol?
        # If we REPLACE, we lose old columns if not provided?
        # Yes, REPLACE deletes and inserts.
        # So we should use UPDATE if exists, else INSERT.
        # Or better: read `last_exit_reason` and `last_exit_ts` before replace, pass them back?
        # Or use ON CONFLICT UPDATE logic (Upsert). `INSERT ... ON CONFLICT(symbol) DO UPDATE SET ...`
        
        cursor.execute("""
            INSERT INTO positions (
                symbol, entry_ts, entry_price, qty, notional_usdt, 
                sl_pct, tp_pct, status, pattern_id, exit_profile_id, exit_params_json,
                update_ts, side, protective_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, 'LONG', 'NONE')
            ON CONFLICT(symbol) DO UPDATE SET
                entry_ts=excluded.entry_ts,
                entry_price=excluded.entry_price,
                qty=excluded.qty,
                notional_usdt=excluded.notional_usdt,
                status='OPEN',
                update_ts=excluded.update_ts,
                protective_status='NONE'
        """, (
            symbol, entry_ts.isoformat(), entry_price, qty, notional,
            sl_pct, tp_pct, pattern_id, exit_profile_id, 
            json.dumps(exit_params) if exit_params else "{}",
            datetime.now(timezone.utc).isoformat()
        ))
        
        conn.commit()
        conn.close()

    def mark_position_closed(self, symbol: str, close_ts: datetime, close_price: float, pnl: float = 0.0, exit_reason: str = "MANUAL"):
        """Mark position CLOSED and audit."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        ts_str = close_ts.isoformat()
        
        # Update positions
        cursor.execute("""
            UPDATE positions SET 
                status='CLOSED', 
                update_ts=?, 
                last_exit_reason=?,
                last_exit_ts=?
            WHERE symbol=?
        """, (ts_str, exit_reason, ts_str, symbol))
        
        # Audit
        cursor.execute("""
            INSERT INTO trade_audit (symbol, close_ts, pnl, exit_reason)
            VALUES (?, ?, ?, ?)
        """, (symbol, ts_str, pnl, exit_reason))
        
        conn.commit()
        conn.close()

    def set_protective_orders(self, symbol: str, sl_order_id: str = None, tp_order_id: str = None,
                              sl_client_id: str = None, tp_client_id: str = None, status: str = "PLACED"):
        """Update position with protective order info."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE positions 
            SET sl_order_id=?, tp_order_id=?, sl_client_order_id=?, tp_client_order_id=?, protective_status=?, update_ts=?
            WHERE symbol=?
        """, (sl_order_id, tp_order_id, sl_client_id, tp_client_id, status, datetime.now(timezone.utc).isoformat(), symbol))
        conn.commit()
        conn.close()

    def clear_protective_orders(self, symbol: str, status: str = "CANCELLED"):
        """Clear protective orders from position (e.g. after close)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE positions 
            SET sl_order_id=NULL, tp_order_id=NULL, sl_client_order_id=NULL, tp_client_order_id=NULL, protective_status=?, update_ts=?
            WHERE symbol=?
        """, (status, datetime.now(timezone.utc).isoformat(), symbol))
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

    def get_today_net_pnl(self, date_str: Optional[str] = None) -> float:
        """
        Get net PnL for a specific date (YYYY-MM-DD).
        Defaults to today UTC.
        """
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # close_ts like '2025-12-18T...'
        # Check substring match
        query = "SELECT SUM(pnl) FROM trade_audit WHERE substr(close_ts, 1, 10) = ?"
        cursor.execute(query, (date_str,))
        
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
