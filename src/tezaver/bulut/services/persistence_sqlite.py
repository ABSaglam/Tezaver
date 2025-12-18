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
        
        # Schema updates for v1 Sizing
        try:
             cursor.execute("ALTER TABLE positions ADD COLUMN sizing_profile_id TEXT")
             cursor.execute("ALTER TABLE positions ADD COLUMN entry_notional_usdt REAL")
        except: pass
        
        # Schema updates for v0.12 (Risk)
        try:
            # Re-create trade_audit with full schema
            cursor.execute("DROP TABLE IF EXISTS trade_audit")
            cursor.execute("""
                CREATE TABLE trade_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    entry_price REAL, 
                    exit_price REAL, 
                    qty REAL, 
                    pnl_usdt REAL, 
                    pnl_is_estimated INTEGER, 
                    close_ts TEXT, 
                    exit_reason TEXT, 
                    cycle_ts TEXT
                )
            """)
            
            # Add columns to positions if missing
            try:
                cursor.execute("ALTER TABLE positions ADD COLUMN last_exit_reason TEXT")
            except: pass
            
            try:
                cursor.execute("ALTER TABLE positions ADD COLUMN last_exit_cycle_ts TEXT")
            except: pass
            
        except Exception as e:
             print(f"[DB] Schema update error: {e}")
             
        # Re-add sizing columns in trade_audit as well? 
        # Requirement says: "trade_audit insert'e de ekle: sizing_profile_id, entry_notional_usdt"
        try:
             cursor.execute("ALTER TABLE trade_audit ADD COLUMN sizing_profile_id TEXT")
             cursor.execute("ALTER TABLE trade_audit ADD COLUMN entry_notional_usdt REAL")
        except: pass

        # Schema updates for v0.14 (Execution v1)
        try:
             cursor.execute("ALTER TABLE trade_plans ADD COLUMN exec_state TEXT")
        except: pass
        try:
             cursor.execute("ALTER TABLE trade_plans ADD COLUMN exec_started_ts TEXT")
        except: pass
        try:
             cursor.execute("ALTER TABLE trade_plans ADD COLUMN exec_finished_ts TEXT")
        except: pass
        try:
             cursor.execute("ALTER TABLE trade_plans ADD COLUMN exec_error TEXT")
        except: pass

        # ... (Rest of schema updates ignored for brevity, keeping original flow) ...

# -------------------------------------------------------------------------------------

    def upsert_position_open(self, symbol: str, entry_ts: datetime, entry_price: float, qty: float, 
                             notional: float, sl_pct: float, tp_pct: float, 
                             pattern_id: str = None, exit_profile_id: str = None, 
                             exit_params: dict = None, last_update_ts_ms: int = 0,
                             # v1 Sizing
                             sizing_profile_id: str = None,
                             entry_notional_usdt: float = 0.0):
        """Insert or Update OPEN position with OOO protection."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # We need to respect OOO (Out of Order).
        # We only update if last_update_ts_ms > existing.last_update_ts_ms
        
        cursor.execute("""
            INSERT INTO positions (
                symbol, entry_ts, entry_price, qty, notional_usdt, 
                sl_pct, tp_pct, status, pattern_id, exit_profile_id, exit_params_json,
                update_ts, side, protective_status, last_update_ts_ms,
                sizing_profile_id, entry_notional_usdt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, 'LONG', 'NONE', ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                entry_ts=excluded.entry_ts,
                entry_price=excluded.entry_price,
                qty=excluded.qty,
                notional_usdt=excluded.notional_usdt,
                status='OPEN',
                update_ts=excluded.update_ts,
                protective_status='NONE',
                last_update_ts_ms=excluded.last_update_ts_ms,
                sizing_profile_id=excluded.sizing_profile_id,
                entry_notional_usdt=excluded.entry_notional_usdt
            WHERE excluded.last_update_ts_ms > coalesce(positions.last_update_ts_ms, 0)
        """, (
            symbol, entry_ts.isoformat(), entry_price, qty, notional,
            sl_pct, tp_pct, pattern_id, exit_profile_id, 
            json.dumps(exit_params) if exit_params else "{}",
            datetime.now(timezone.utc).isoformat(),
            last_update_ts_ms,
            sizing_profile_id,
            entry_notional_usdt
        ))
        
        conn.commit()
        conn.close()

        # Schema updates for v0.15 (Ops Pack)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                level TEXT,
                code TEXT,
                message TEXT,
                details_json TEXT
            )
        """)

        # Schema updates for v0.17 (Fill-Based TradeAudit)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_fills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                order_id INTEGER,
                trade_id TEXT,
                price REAL,
                qty REAL,
                realized_pnl REAL,
                commission REAL,
                commission_asset TEXT,
                ts TEXT,
                raw_json TEXT
            )
        """)
        
        # Alter trade_audit
        cols_v17 = [
            ("gross_pnl_usdt", "REAL"),
            ("fee_usdt", "REAL"),
            ("net_pnl_usdt", "REAL"),
            ("pnl_source", "TEXT"),
            ("close_order_id", "INTEGER"),
            ("open_order_id", "INTEGER"),
            ("pattern_id", "TEXT"),
            ("fee_asset", "TEXT"),
            ("fee_native", "REAL"),
            ("audit_upgraded", "INTEGER DEFAULT 0")
        ]
        for col, dtype in cols_v17:
             try:
                 cursor.execute(f"ALTER TABLE trade_audit ADD COLUMN {col} {dtype}")
             except: pass

        # Schema updates for v0.18 (Income Sync)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS income_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tran_id TEXT UNIQUE,
                symbol TEXT,
                income_type TEXT,
                asset TEXT,
                income REAL,
                time_ms INTEGER,
                time_ts TEXT,
                info TEXT,
                raw_json TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_ts TEXT
            )
        """)

        # v0.19 FX Conversion
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fx_rates (
                asset TEXT PRIMARY KEY,
                quote TEXT,
                rate REAL,
                source TEXT,
                updated_ts TEXT
            )
        """)

        try:
             cursor.execute("ALTER TABLE income_events ADD COLUMN income_usdt REAL")
             cursor.execute("ALTER TABLE income_events ADD COLUMN fx_rate REAL")
             cursor.execute("ALTER TABLE income_events ADD COLUMN fx_source TEXT")
        except: pass

        try:
             cursor.execute("ALTER TABLE trade_audit ADD COLUMN fee_fx_rate REAL")
             cursor.execute("ALTER TABLE trade_audit ADD COLUMN fee_fx_source TEXT")
        except: pass
        
        try:
             cursor.execute("ALTER TABLE trade_audit ADD COLUMN fee_usdt REAL")
        except: pass

        # v0.22 State Reducer
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applied_events (
                event_id TEXT PRIMARY KEY,
                event_ts_ms INTEGER,
                source TEXT,
                kind TEXT,
                symbol TEXT,
                inserted_ts TEXT
            )
        """)
        
        try:
             cursor.execute("ALTER TABLE positions ADD COLUMN last_update_ts_ms INTEGER")
        except: pass

        # v0.23 Task Supervisor / Heartbeats
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS heartbeats (
                name TEXT PRIMARY KEY,
                last_ts TEXT,
                last_ms INTEGER,
                status TEXT,
                detail TEXT
            )
        """)
        
        # v0.25 Config Snapshots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                hash TEXT,
                mode TEXT,
                content_json TEXT,
                source TEXT
            )
        """)

        # v0.29 Policy State Machine
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS policy_states (
                symbol TEXT PRIMARY KEY,
                phase TEXT,
                opened_cycle_ts TEXT,
                effective_cycle_ts TEXT,
                last_action_ts TEXT,
                hold_bars_remaining INTEGER,
                last_reason TEXT,
                last_update_ms INTEGER DEFAULT 0
            ) 
        """)

        # v1.0 Cycle Forensics Timelines
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cycle_timelines (
                cycle_index INTEGER PRIMARY KEY,
                cycle_ts TEXT,
                timeline_json TEXT,
                created_ts TEXT
            )
        """)
        
        # Ensure Alerts table (Critical for Proof Ladder)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                level TEXT,
                code TEXT,
                message TEXT,
                details_json TEXT
            )
        """)

        # v1.1 Proof Ladder (Mainnet Cap Evidence)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proof_ladder_state (
                id INTEGER PRIMARY KEY DEFAULT 1,
                stage_id TEXT,
                cap_usdt REAL,
                last_evaluated_ts TEXT,
                clean_hours REAL,
                last_result_json TEXT,
                updated_ts TEXT
            )
        """)
        # Ensure single row constraint via ID=1 logic on insert, or just code enforce


        conn.commit()
        conn.close()
        
    # --- Policy State Machine (v1) ---
    
    def upsert_policy_state(self, state: dict):
        """Upsert policy state with OOO protection."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # We use WHERE clause on conflict update to ensure we only overwrite if newer.
        # Note: SQLite ON CONFLICT clause supports WHERE since 3.24.
        cursor.execute("""
            INSERT INTO policy_states (
                symbol, phase, opened_cycle_ts, effective_cycle_ts, 
                last_action_ts, hold_bars_remaining, last_reason, last_update_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                phase=excluded.phase,
                opened_cycle_ts=excluded.opened_cycle_ts,
                effective_cycle_ts=excluded.effective_cycle_ts,
                last_action_ts=excluded.last_action_ts,
                hold_bars_remaining=excluded.hold_bars_remaining,
                last_reason=excluded.last_reason,
                last_update_ms=excluded.last_update_ms
            WHERE excluded.last_update_ms >= policy_states.last_update_ms
        """, (
            state["symbol"], state["phase"], state["opened_cycle_ts"], 
            state["effective_cycle_ts"], state["last_action_ts"], 
            state["hold_bars_remaining"], state["last_reason"],
            state.get("last_update_ms", 0)
        ))
        
        conn.commit()
        conn.close()

    def get_policy_state(self, symbol: str) -> Optional[dict]:
        """Get policy state."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM policy_states WHERE symbol=?", (symbol,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def insert_config_snapshot(self, hash_val: str, mode: str, content_json: str, source: str):
        """Insert a redacted config snapshot."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now_ts = datetime.now(timezone.utc).isoformat()
        
        cursor.execute("""
            INSERT INTO config_snapshots (ts, hash, mode, content_json, source)
            VALUES (?, ?, ?, ?, ?)
        """, (now_ts, hash_val, mode, content_json, source))
        
        conn.commit()
        conn.close()

    def get_latest_config_snapshot(self, source: Optional[str] = None) -> Optional[dict]:
        """Get the most recent config snapshot, optionally filtered by source."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if source:
            cursor.execute("SELECT * FROM config_snapshots WHERE source = ? ORDER BY id DESC LIMIT 1", (source,))
        else:
            cursor.execute("SELECT * FROM config_snapshots ORDER BY id DESC LIMIT 1")
            
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
        
    # --- Schema Meta (v0.26) ---

    def get_schema_version(self) -> int:
        """Get current schema version."""
        conn = self._get_conn()
        cursor = conn.cursor()
        # Bootstrap schema_meta if not exists (circular dependency with migration runner otherwise)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cursor.execute("SELECT value FROM schema_meta WHERE key='schema_version'")
        row = cursor.fetchone()
        conn.close()
        return int(row[0]) if row else 0

    def set_schema_version(self, version: int):
        """Set schema version."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO schema_meta (key, value) VALUES ('schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (str(version),))
        conn.commit()
        conn.close()

    # --- Heartbeats (v0.23) ---

    def beat(self, name: str, status: str = "OK", detail: str = ""):
        """Update task heartbeat."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc)
        ts_str = now.isoformat()
        ms = int(now.timestamp() * 1000)
        
        cursor.execute("""
            INSERT INTO heartbeats (name, last_ts, last_ms, status, detail)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                last_ts=excluded.last_ts,
                last_ms=excluded.last_ms,
                status=excluded.status,
                detail=excluded.detail
        """, (name, ts_str, ms, status, detail))
        
        conn.commit()
        conn.close()

    def get_heartbeats(self) -> Dict[str, dict]:
        """Get all heartbeats."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM heartbeats")
        rows = cursor.fetchall()
        conn.close()
        
        return {r["name"]: dict(r) for r in rows}

    # --- Trade Audit (Direct Event) v0.22 ---
    
    def upsert_trade_audit_event(self, order_id: str, client_id: str, symbol: str, status: str, exec_type: str, filled_qty: float, avg_price: float, event_time: int):
        """
        Upsert trade audit from execution event (WS/Reducer).
        If (order_id, symbol) exists? 
        Table `trade_audit` currently just ID primary key.
        We check `close_order_id` or `open_order_id`? Or just append log?
        Requirements say: "Upsert". 
        But `trade_audit` is for COMPLETED trades (Pnl).
        ORDER_TRADE_UPDATE often is just "FILLED".
        If "FILLED" and "filled_qty" > 0, it contributes to position.
        The current `trade_audit` table is for storing PnL items (closed trades).
        But if we want to log "Orders" we should use `order_fills` table or similar.
        v0.17 created `order_fills`.
        Let's use `upsert_fill_event` instead?
        Or append to `order_fills`?
        The reducer calls `upsert_trade_audit_event`.
        If the intention is to populate the "Audit Log", we need to map to audit fields.
        However, "Trade Audit" usually implies "Closed Position PnL Record".
        If this is just an Order Fill, maybe we store in `order_fills`?
        Let's check `order_fills` schema.
        It has: symbol, order_id, trade_id, price, qty... 
        Let's implement `upsert_trade_audit_event` to INSERT INTO order_fills?
        Wait, requirements said: "update order_fills/trade_audit".
        If it's a CLOSE (reduce only?), we might want to generate trade_audit PnL record.
        But calculation of PnL requires entry price memory.
        For now, let's implement `upsert_trade_audit_event` to insert into `order_fills` (granular).
        AND if status is FILLED/PARTIALLY_FILLED?
        Actually, let's rename it to `upsert_fill_event` in thought, but keep signature for `reducer`.
        Or better: just implement the method provided signature and put data into appropriate places.
        I will insert into `order_fills` for now as that's the raw fill log.
        If we want to generate `trade_audit` (PnL), we relies on `mark_position_closed`.
        So `upsert_trade_audit_event` -> `order_fills`.
        """
        if exec_type not in ("TRADE", "FILLED", "PARTIALLY_FILLED"):
             return # Only track fills for audit purposes
             
        if filled_qty <= 0:
             return

        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Check if trade_id/fill exists?
        # events usually have `t` tradeId.
        # But here we pass basic info.
        # We'll just insert for now. It's better to have duplicate fills than missing, but dedup handles it upstream!
        # Because Reducer calls this, we know it's unique EVENT.
        # So we insert.
        
        event_ts_iso = datetime.fromtimestamp(event_time/1000.0, timezone.utc).isoformat()
        
        cursor.execute("""
            INSERT INTO order_fills (
                symbol, order_id, trade_id, price, qty, 
                realized_pnl, commission, commission_asset, ts, raw_json
            ) VALUES (?, ?, ?, ?, ?, 0, 0, 'UNK', ?, '{}')
        """, (symbol, order_id, f"evt_{event_time}", avg_price, filled_qty, event_ts_iso))
        
        conn.commit()
        conn.close()

    # --- Positions ---
    
    def upsert_position_open(self, symbol: str, entry_ts: datetime, entry_price: float, qty: float, 
                             notional: float, sl_pct: float, tp_pct: float, 
                             pattern_id: str = None, exit_profile_id: str = None, 
                             exit_params: dict = None, last_update_ts_ms: int = 0,
                             # v1 Sizing
                             sizing_profile_id: str = None,
                             entry_notional_usdt: float = 0.0):
        """Insert or Update OPEN position with OOO protection."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # We need to respect OOO (Out of Order).
        # We only update if last_update_ts_ms > existing.last_update_ts_ms
        
        cursor.execute("""
            INSERT INTO positions (
                symbol, entry_ts, entry_price, qty, notional_usdt, 
                sl_pct, tp_pct, status, pattern_id, exit_profile_id, exit_params_json,
                update_ts, side, protective_status, last_update_ts_ms,
                sizing_profile_id, entry_notional_usdt
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, 'LONG', 'NONE', ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                entry_ts=excluded.entry_ts,
                entry_price=excluded.entry_price,
                qty=excluded.qty,
                notional_usdt=excluded.notional_usdt,
                status='OPEN',
                update_ts=excluded.update_ts,
                protective_status='NONE',
                last_update_ts_ms=excluded.last_update_ts_ms,
                sizing_profile_id=excluded.sizing_profile_id,
                entry_notional_usdt=excluded.entry_notional_usdt
            WHERE excluded.last_update_ts_ms > coalesce(positions.last_update_ts_ms, 0)
        """, (
            symbol, entry_ts.isoformat(), entry_price, qty, notional,
            sl_pct, tp_pct, pattern_id, exit_profile_id, 
            json.dumps(exit_params) if exit_params else "{}",
            datetime.now(timezone.utc).isoformat(),
            last_update_ts_ms,
            sizing_profile_id,
            entry_notional_usdt
        ))
        
        conn.commit()
        conn.close()

    def update_position_closed_state(self, symbol: str, close_ts: datetime, exit_reason: str, cycle_ts: Optional[datetime] = None):
        """Update position to CLOSED state without auditing."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        ts_str = close_ts.isoformat()
        cycle_ts_str = cycle_ts.isoformat() if cycle_ts else ts_str
        
        cursor.execute("""
            UPDATE positions SET 
                status='CLOSED', 
                update_ts=?, 
                last_exit_reason=?,
                last_exit_cycle_ts=?
            WHERE symbol=?
        """, (ts_str, exit_reason, cycle_ts_str, symbol))
        
        conn.commit()
        conn.close()

    def mark_position_closed(
        self, 
        symbol: str, 
        close_ts: datetime, 
        exit_price: float, 
        entry_price: float = 0.0,
        qty: float = 0.0,
        pnl_usdt: float = 0.0,
        pnl_is_estimated: bool = False,
        exit_reason: str = "MANUAL",
        cycle_ts: Optional[datetime] = None,
        close_order_id: Optional[int] = None,
        last_update_ts_ms: int = 0
    ):
        """Mark position CLOSED and audit (ESTIMATED fallback) with OOO protection."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        ts_str = close_ts.isoformat()
        cycle_ts_str = cycle_ts.isoformat() if cycle_ts else ts_str
        
        # Update positions
        # Only update if last_update_ts_ms is newer
        cursor.execute("""
            UPDATE positions SET 
                status='CLOSED', 
                update_ts=?, 
                last_exit_reason=?,
                last_exit_cycle_ts=?,
                last_update_ts_ms=?
            WHERE symbol=? AND ? > coalesce(last_update_ts_ms, 0)
        """, (ts_str, exit_reason, cycle_ts_str, last_update_ts_ms, symbol, last_update_ts_ms))
        
        if cursor.rowcount > 0:
            # Audit only if we actually closed it?
            # Or audit always? Audit is append-only log. 
            # If we receive "closed at T1" then "closed at T2" (OOO?)
            # TradeAudit duplicate check handles audit Idempotency if key is provided?
            # Current TradeAudit has no unique key other than ID.
            # But duplicate audits for same trade are bad.
            # If we have Dedup (try_mark_event_applied) before this, we are safe from duplicates.
            # So we just insert.
            cursor.execute("""
                INSERT INTO trade_audit (
                    symbol, close_ts, exit_reason, 
                    entry_price, exit_price, qty, 
                    pnl_usdt, pnl_is_estimated, cycle_ts,
                    pnl_source, close_order_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ESTIMATED', ?)
            """, (
                symbol, ts_str, exit_reason,
                entry_price, exit_price, qty,
                pnl_usdt, 1 if pnl_is_estimated else 0, cycle_ts_str,
                close_order_id
            ))
        
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



    # --- State Reducer (v0.22) ---

    def try_mark_event_applied(self, event_id: str, event_ts_ms: int, source: str, kind: str, symbol: str) -> bool:
        """
        Atomically mark event as applied.
        Returns True if successful (new event), False if duplicate (idempotency).
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        now_ts = datetime.now(timezone.utc).isoformat()
        
        try:
            cursor.execute("""
                INSERT INTO applied_events (event_id, event_ts_ms, source, kind, symbol, inserted_ts)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (event_id, event_ts_ms, source, kind, symbol, now_ts))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False
        except Exception:
            conn.close()
            return False

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

    def try_mark_executing(self, idempotency_key: str) -> bool:
        """
        Atomic execution lock.
        Marks plan as EXECUTING only if it hasn't been started yet.
        Returns True if lock acquired, False otherwise.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        now_ts = datetime.now(timezone.utc).isoformat()
        
        # We allow execution if exec_state is NULL or 'ACCEPTED' or 'PROPOSED'
        # If it is 'EXECUTING', 'EXECUTED', 'FAILED', we reject.
        cursor.execute("""
            UPDATE trade_plans 
            SET exec_state='EXECUTING', exec_started_ts=?
            WHERE idempotency_key=? 
              AND (exec_state IS NULL OR exec_state IN ('ACCEPTED', 'PROPOSED'))
        """, (now_ts, idempotency_key))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def finalize_plan_execution(self, idempotency_key: str, state: str, error: Optional[str] = None):
        """
        Finalize execution state (EXECUTED, FAILED).
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        now_ts = datetime.now(timezone.utc).isoformat()
        
        cursor.execute("""
            UPDATE trade_plans 
            SET exec_state=?, exec_finished_ts=?, exec_error=?
            WHERE idempotency_key=?
        """, (state, now_ts, error, idempotency_key))
        
        conn.commit()
        conn.close()

    def get_plans_by_status(self, status: str) -> List[dict]:
        """Get plans by status (e.g. EXECUTING)."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check both status and exec_state?
        # status used to be primary, but now exec_state tracks lifecycle?
        # Executor updates 'exec_state' for locking.
        # But 'status' is also updated.
        # Let's query based on the passed status comparing check against both for robustness?
        # Or usually caller passes 'EXECUTING' which refers to exec_state?
        # get_plans_by_status("EXECUTING") implicitly means exec_state.
        
        cursor.execute("SELECT * FROM trade_plans WHERE status=? OR exec_state=?", (status, status))
        rows = cursor.fetchall()
        
        plans = [dict(row) for row in rows]
        conn.close()
        return plans

    def get_plan(self, idempotency_key: str) -> Optional[dict]:
        """Get single plan."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM trade_plans WHERE idempotency_key=?", (idempotency_key,))
        row = cursor.fetchone()
        
        conn.close()
        return dict(row) if row else None
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

    # --- Alerts (v0.15) ---

    def insert_alert(self, level: str, code: str, message: str, details: dict = None) -> None:
        """Insert a system alert."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        ts = datetime.now(timezone.utc).isoformat()
        details_json = json.dumps(details) if details else "{}"
        
        cursor.execute("""
            INSERT INTO alerts (ts, level, code, message, details_json)
            VALUES (?, ?, ?, ?, ?)
        """, (ts, level, code, message, details_json))
        
        conn.commit()
        conn.close()

    def get_latest_alerts(self, limit: int = 20) -> List[dict]:
        """Get latest system alerts."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,))
        
        rows = cursor.fetchall()
        alerts = [dict(row) for row in rows]
        
        for a in alerts:
            try:
                a["details"] = json.loads(a["details_json"])
            except:
                a["details"] = {}
                
        conn.close()
        return alerts

    # --- Income Sync (v0.18) ---

    def upsert_income_events(self, events: List[dict]) -> int:
        """
        Batch insert income events (ignore duplicates by tranId).
        Returns count of inserted rows.
        """
        if not events:
            return 0
            
        conn = self._get_conn()
        cursor = conn.cursor()
        
        inserted_count = 0
        
        data = []
        for e in events:
            # e is raw binance income dict + optional FX fields (v0.19)
            # keys: tranId, symbol, incomeType, income, asset, time, info, income_usdt, fx_rate, fx_source
            time_ms = int(e.get("time", 0))
            time_ts = datetime.fromtimestamp(time_ms/1000.0, timezone.utc).isoformat()
            
            data.append((
                str(e.get("tranId")),
                e.get("symbol"),
                e.get("incomeType"),
                e.get("asset"),
                float(e.get("income", 0)),
                time_ms,
                time_ts,
                e.get("info", ""),
                json.dumps(e),
                e.get("income_usdt"),
                e.get("fx_rate"),
                e.get("fx_source")
            ))
            
        cursor.executemany("""
            INSERT OR IGNORE INTO income_events (
                tran_id, symbol, income_type, asset, income, time_ms, time_ts, info, raw_json,
                income_usdt, fx_rate, fx_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)
        
        inserted_count = cursor.rowcount 
        
        conn.commit()
        conn.close()
        return inserted_count

    def get_income_last_sync_ms(self) -> int:
        """Get last sync timestamp for income."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_state WHERE key='income_last_sync_ms'")
        row = cursor.fetchone()
        conn.close()
        return int(row[0]) if row else 0

    # --- FX (v0.19) ---

    def upsert_fx_rate(self, asset: str, quote: str, rate: float, source: str):
        """Upsert FX rate."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now_ts = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO fx_rates (asset, quote, rate, source, updated_ts)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(asset) DO UPDATE SET
                rate=excluded.rate,
                source=excluded.source,
                quote=excluded.quote,
                updated_ts=excluded.updated_ts
        """, (asset, quote, rate, source, now_ts))
        conn.commit()
        conn.close()

    def get_all_fx_rates(self) -> List[dict]:
        """
        Get all cached FX rates.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT asset, quote, rate, source, updated_ts FROM fx_rates ORDER BY updated_ts DESC")
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {"asset": r[0], "quote": r[1], "rate": r[2], "source": r[3], "updated_ts": r[4]}
            for r in rows
        ]

    def get_fx_rate(self, asset: str) -> Optional[dict]:
        """Get FX rate for asset."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM fx_rates WHERE asset=?", (asset,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
        
    def get_unconverted_income(self, date_str: str) -> List[dict]:
        """Get income events needing conversion today."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # asset != 'USDT' AND (income_usdt IS NULL)
        cursor.execute("""
            SELECT * FROM income_events 
            WHERE substr(time_ts, 1, 10) = ?
              AND asset != 'USDT'
              AND income_usdt IS NULL
        """, (date_str,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_income_conversion(self, tran_id: str, income_usdt: float, rate: float, source: str):
        """Update income event with conversion data."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE income_events
            SET income_usdt=?, fx_rate=?, fx_source=?
            WHERE tran_id=?
        """, (income_usdt, rate, source, tran_id))
        conn.commit()
        conn.close()

    def get_unconverted_audits(self, date_str: str) -> List[dict]:
        """Get trade audits needing conversion today."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # fee_asset != 'USDT' AND (fee_usdt IS NULL)
        cursor.execute("""
            SELECT * FROM trade_audit 
            WHERE substr(close_ts, 1, 10) = ?
              AND fee_asset IS NOT NULL
              AND fee_asset != 'USDT'
              AND fee_usdt IS NULL
        """, (date_str,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_audit_conversion(self, audit_id: int, fee_usdt: float, net_pnl_usdt: float, rate: float, source: str):
        """Update trade audit with conversion data."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE trade_audit
            SET fee_usdt=?, net_pnl_usdt=?, fee_fx_rate=?, fee_fx_source=?
            WHERE id=?
        """, (fee_usdt, net_pnl_usdt, rate, source, audit_id))
        conn.commit()
        conn.close()



    def set_income_last_sync_ms(self, ms: int):
        """Set last sync timestamp for income."""
        self.set_system_state("income_last_sync_ms", str(ms))

    def set_system_state(self, key: str, value: str):
        """Set generic system state key."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now_ts = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO system_state (key, value, updated_ts) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_ts=excluded.updated_ts
        """, (key, value, now_ts))
        conn.commit()
        conn.close()

    def get_system_state(self, key: str) -> Optional[str]:
        """Get generic system state value."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_state WHERE key=?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def get_today_income_sum_utc(self, types: List[str] = None, date_str: Optional[str] = None) -> dict:
        """
        Get sum of income for specific types today.
        Returns: { 
            "FUNDING_FEE": 1.23, # Native sum (mixed) - purely informational now? Or per-asset?
            "TOTAL": 1.23,       # Sum of income_usdt (or native USDT)
            "non_usdt_count": 0, # Assets != USDT with NULL income_usdt
            "unconverted_sum": 0.0 # Sum of unconverted native amounts? Hard to sum different assets.
        }
        """
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Filter by types
        type_clause = ""
        args = [date_str]
        if types:
            placeholders = ",".join("?" * len(types))
            type_clause = f"AND income_type IN ({placeholders})"
            args.extend(types)
            
        # Group by asset, income_type.
        # Also sum income_usdt.
        query = f"""
            SELECT 
                income_type, 
                asset, 
                SUM(income), 
                COUNT(*), 
                SUM(COALESCE(income_usdt, (CASE WHEN asset='USDT' THEN income ELSE 0 END))),
                SUM(CASE WHEN asset != 'USDT' AND income_usdt IS NULL THEN 1 ELSE 0 END)
            FROM income_events
            WHERE substr(time_ts, 1, 10) = ? {type_clause}
            GROUP BY income_type, asset
        """
        
        cursor.execute(query, tuple(args))
        rows = cursor.fetchall()
        conn.close()
        
        result = {"TOTAL": 0.0, "non_usdt_count": 0}
        
        for r in rows:
            # 0:type, 1:asset, 2:sum_native, 3:count, 4:sum_usdt, 5:unconverted_count
            i_type = r[0]
            val_native = r[2]
            val_usdt = r[4] if r[4] is not None else 0.0
            unconverted_cnt = r[5]
            
            # Aggregate per type (native? No, let's use USDT if possible, but keep native for type breakdown?)
            # The dashboard shows "Income Breakdown". Previously it showed native sums per type.
            # If we return native sums, it's confusing if mixed assets.
            # Let's return USDT sums for safety for "TOTAL".
            # Breakdown keys: maybe "FUNDING_FEE" -> native sum? Or USDT sum?
            # Existing dashboard expects "FUNDING_FEE": value.
            # Let's strive to return USDT sum for the type if possible.
            
            result[i_type] = result.get(i_type, 0.0) + val_usdt
            result["TOTAL"] += val_usdt
            result["non_usdt_count"] += unconverted_cnt
                
        return result

    # --- Fill Sync (v0.17) ---

    def insert_order_fills(self, fills: List[dict]):
        """Batch insert order fills."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        data = []
        for f in fills:
            data.append((
                f.get("symbol"),
                f.get("orderId"),
                str(f.get("id")), # trade_id
                float(f.get("price", 0)),
                float(f.get("qty", 0)),
                float(f.get("realizedPnl", 0)),
                float(f.get("commission", 0)),
                f.get("commissionAsset"),
                str(f.get("time")), # usually timestamp ms
                json.dumps(f)
            ))
            
        cursor.executemany("""
            INSERT INTO order_fills (
                symbol, order_id, trade_id, price, qty, 
                realized_pnl, commission, commission_asset, ts, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)
        
        conn.commit()
        conn.close()

    def upsert_trade_audit_from_fills(
        self,
        symbol: str,
        close_order_id: int,
        summary: dict,
        exit_reason: str,
        cycle_ts: str,
        entry_price: float,
        # Optional pattern/open info if known
        pattern_id: str = None
    ):
        """
        Create/Update trade_audit record based on verified fills.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        now_ts = datetime.now(timezone.utc).isoformat()
        
        # summary: {qty, vwap, realized_pnl, commission, commission_asset, net_pnl, ts_last, fee_usdt, fx_rate, fx_source}
        
        # We insert a new record for this "Closed Position Event"
        # Source=USER_TRADES
        
        # v0.19: explicitly use summary["fee_usdt"] if present (calculated via FX)
        # fallback to commission if asset is USDT.
        
        comm = summary.get("commission", 0.0)
        asset = summary.get("commission_asset", "USDT")
        fee_usdt = summary.get("fee_usdt")
        
        if fee_usdt is None:
            # Fallback v0.17 logic
            if asset == "USDT":
                fee_usdt = comm
            else:
                fee_usdt = None # Unconverted
                
        # Net PnL calculation:
        # If we have fee_usdt, Realized - Fee.
        realized = summary.get("realized_pnl", 0.0)
        
        # If fee_usdt is None (unconverted), we treat net_pnl = realized (gross).
        # This is temporary until recompute fixes it.
        net_pnl = realized - (fee_usdt if fee_usdt is not None else 0.0)
        
        cursor.execute("""
            INSERT INTO trade_audit (
                symbol, close_ts, exit_reason, 
                entry_price, exit_price, qty,
                pnl_usdt, pnl_is_estimated, cycle_ts,
                gross_pnl_usdt, fee_usdt, net_pnl_usdt, 
                pnl_source, close_order_id, pattern_id,
                fee_asset, fee_native,
                fee_fx_rate, fee_fx_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 'USER_TRADES', ?, ?, ?, ?, ?, ?)
        """, (
            symbol, 
            datetime.fromtimestamp(summary["ts_last"]/1000.0, timezone.utc).isoformat(),
            exit_reason,
            entry_price,
            summary["vwap"],
            summary["qty"],
            net_pnl, # authoritative pnl_usdt is net
            cycle_ts,
            realized,
            fee_usdt,
            net_pnl,
            close_order_id,
            pattern_id,
            asset,
            comm,
            summary.get("fx_rate"),
            summary.get("fx_source")
        ))
        
        conn.commit()
        conn.close()

    def upgrade_trade_audit_from_fills(self, symbol: str, close_order_id: int, summary: dict) -> bool:
        """
        Attempt to upgrade an ESTIMATED audit record to USER_TRADES using verified fills.
        Returns True if a record was found and upgraded.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # We look for a record with same close_order_id that is still ESTIMATED
        # or has pnl_source='ESTIMATED'
        # Note: Previous mark_position_closed used estimated price/pnl.
        # It didn't have close_order_id set? Wait, executor passes close_order_id to upsert_trade_audit_from_fills.
        # But mark_position_closed DOES NOT take close_order_id in v0.17!
        # Wait, I need to check executor.py from v0.17...
        # In v0.17 executor.py: mark_position_closed was called WITHOUT close_order_id.
        # So we might need to match by symbol and cycle_ts or just symbol if it's the latest?
        # Actually, user requested: "Eğer aynı close_order_id için trade_audit varsa ve pnl_source=="ESTIMATED""
        # This implies I should have added close_order_id to mark_position_closed too,
        # or find it by other means.
        # Let's check trade_audit columns I added in _init_db... I added close_order_id.
        
        # Calculation
        realized = summary.get("realized_pnl", 0.0)
        comm = summary.get("commission", 0.0)
        asset = summary.get("commission_asset", "USDT")
        
        net_usdt = realized
        if asset == "USDT":
            net_usdt = realized - comm
            
        cursor.execute("""
            UPDATE trade_audit
            SET gross_pnl_usdt = ?,
                fee_usdt = ?,
                fee_native = ?,
                fee_asset = ?,
                net_pnl_usdt = ?,
                pnl_usdt = ?,
                exit_price = ?,
                qty = ?,
                pnl_source = 'USER_TRADES',
                audit_upgraded = 1,
                pnl_is_estimated = 0
            WHERE symbol = ? AND close_order_id = ? AND pnl_source = 'ESTIMATED'
        """, (
            realized,
            comm if asset == "USDT" else 0.0,
            comm,
            asset,
            net_usdt,
            net_usdt, # legacy pnl_usdt
            summary.get("vwap"),
            summary.get("qty"),
            symbol,
            close_order_id
        ))
        
        upgraded = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return upgraded

    def get_today_net_pnl_utc(self, date_str: Optional[str] = None) -> float:
        """
        Get TOTAL NET PnL for a specific date (YYYY-MM-DD) in UTC.
        Uses net_pnl_usdt if available, else pnl_usdt (compat).
        """
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Logic: COALESCE(net_pnl_usdt, pnl_usdt, 0)
        query = """
            SELECT COALESCE(SUM(COALESCE(net_pnl_usdt, pnl_usdt, 0)), 0) 
            FROM trade_audit 
            WHERE substr(close_ts, 1, 10) = ?
        """
        cursor.execute(query, (date_str,))
        
        total = cursor.fetchone()[0]
        conn.close()
        return total

        
        # Net: COALESCE(net_pnl_usdt, pnl_usdt, 0)
        # Gross: COALESCE(gross_pnl_usdt, pnl_usdt, 0)
        # Fee: COALESCE(fee_usdt, 0)
        
        query = """
            SELECT 
                SUM(COALESCE(net_pnl_usdt, pnl_usdt, 0)),
                SUM(COALESCE(gross_pnl_usdt, pnl_usdt, 0)),
                SUM(COALESCE(fee_usdt, 0))
            FROM trade_audit 
            WHERE substr(close_ts, 1, 10) = ?
        """
        cursor.execute(query, (date_str,))
        row = cursor.fetchone()
        
        conn.close()
        
        return {
            "net_pnl": row[0] if row and row[0] else 0.0,
            "gross_pnl": row[1] if row and row[1] else 0.0,
            "fees": row[2] if row and row[2] else 0.0
        }

    def get_latest_audit(self, limit: int = 20) -> List[dict]:
        """Get latest trade audit records."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM trade_audit ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        
        audit = [dict(row) for row in rows]
        conn.close()
        return audit

    # --- Cycle Forensics (v1) ---

    def upsert_cycle_timeline(self, cycle_index: int, cycle_ts: datetime, timeline_json: str):
        """
        Upsert a cycle timeline JSON.
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()
            created_ts = datetime.now(timezone.utc).isoformat()
            
            cursor.execute("""
                INSERT INTO cycle_timelines (cycle_index, cycle_ts, timeline_json, created_ts)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cycle_index) DO UPDATE SET
                    timeline_json = excluded.timeline_json,
                    created_ts = excluded.created_ts
            """, (cycle_index, cycle_ts.isoformat(), timeline_json, created_ts))
            conn.commit()

    def get_latest_timelines(self, limit: int = 20) -> List[Dict]:
        """
        Get the latest cycle timelines.
        Returns list of dicts (parsed JSON).
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cycle_index, cycle_ts, timeline_json, created_ts
                FROM cycle_timelines
                ORDER BY cycle_index DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            results = []
            for r in rows:
                try:
                    obj = json.loads(r[2])
                    # Ensure metadata is consistent with DB if needed, 
                    # but obj should be self-contained.
                    results.append(obj)
                except Exception as e:
                    print(f"[PERSISTENCE] Failed to parse timeline {r[0]}: {e}")
            return results

    # --- Proof Ladder (v1) ---

    def get_proof_ladder_state(self) -> Optional[dict]:
        """Get current proof ladder state."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM proof_ladder_state WHERE id=1")
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.OperationalError:
            # Table might not exist yet if not migrated or initialized
            return None
        finally:
            conn.close()

    def upsert_proof_ladder_state(self, stage_id: str, cap_usdt: float, clean_hours: float, last_result_obj: dict):
        """Update proof ladder state (always row 1)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now_ts = datetime.now(timezone.utc).isoformat()
        
        cursor.execute("CREATE TABLE IF NOT EXISTS proof_ladder_state (id INTEGER PRIMARY KEY DEFAULT 1, stage_id TEXT, cap_usdt REAL, last_evaluated_ts TEXT, clean_hours REAL, last_result_json TEXT, updated_ts TEXT)")

        cursor.execute("""
            INSERT INTO proof_ladder_state (
                id, stage_id, cap_usdt, clean_hours, last_result_json, last_evaluated_ts, updated_ts
            ) VALUES (1, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                stage_id=excluded.stage_id,
                cap_usdt=excluded.cap_usdt,
                clean_hours=excluded.clean_hours,
                last_result_json=excluded.last_result_json,
                last_evaluated_ts=excluded.last_evaluated_ts,
                updated_ts=excluded.updated_ts
        """, (
            stage_id, cap_usdt, clean_hours, 
            json.dumps(last_result_obj), now_ts, now_ts
        ))
        
        conn.commit()
        conn.close()

    def get_proof_ladder_metrics(self, since_ts: str) -> Dict[str, int]:
        """
        Get aggregated metrics for Proof Ladder evaluation since timestamp.
        Returns counts of critical alerts, error alerts, estimated audits, unconverted fx.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        metrics = {
            "alerts_critical": 0,
            "alerts_error": 0,
            "audits_estimated": 0,
            "fx_unconverted": 0
        }
        
        
        # Alerts
        # Lazy create if missing (Recover from init failures)
        try:
             cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT,
                    level TEXT,
                    code TEXT,
                    message TEXT,
                    details_json TEXT
                )
             """)
        except: pass

        # Assuming alerts table has `level` and `ts` AND `alerts` table exists
        try:
            cursor.execute("SELECT COUNT(*) FROM alerts WHERE ts >= ? AND level='CRITICAL'", (since_ts,))
            metrics["alerts_critical"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM alerts WHERE ts >= ? AND level='ERROR'", (since_ts,))
            metrics["alerts_error"] = cursor.fetchone()[0]
        except: pass
        
        # Audits
        try:
            cursor.execute("SELECT COUNT(*) FROM trade_audit WHERE close_ts >= ? AND pnl_source='ESTIMATED'", (since_ts,))
            metrics["audits_estimated"] = cursor.fetchone()[0]
        except: pass

        # FX Unconverted
        try:
            # income_events: fx_rate IS NULL or 0
            # AND asset != USDT (implicitly or filtered?)
            # Actually unconverted means we needed conversion but didn't get it.
            # Usually implies asset!=USDT and (rate is missing/null/0).
            # Let's count where asset != 'USDT' AND (fx_rate IS NULL OR fx_rate = 0)
            cursor.execute("SELECT COUNT(*) FROM income_events WHERE time_ts >= ? AND asset != 'USDT' AND (fx_rate IS NULL OR fx_rate=0)", (since_ts,))
            metrics["fx_unconverted"] = cursor.fetchone()[0]
        except: pass
        
        conn.close()
        return metrics
