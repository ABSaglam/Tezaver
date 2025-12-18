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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                side TEXT,
                entry_price REAL,
                quantity REAL,
                notional_usdt REAL,
                open_ts TEXT,
                update_ts TEXT
            )
        """)
        
        # Trade Plans table
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
    
    def get_open_positions(self) -> List[dict]:
        """Get all open positions."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM positions")
        rows = cursor.fetchall()
        
        positions = [dict(row) for row in rows]
        conn.close()
        return positions
        
    def get_open_position_count(self) -> int:
        """Get count of open positions."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM positions")
        count = cursor.fetchone()[0]
        conn.close()
        return count
        
    def get_total_notional(self) -> float:
        """Get total notional of open positions."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(notional_usdt) FROM positions")
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
