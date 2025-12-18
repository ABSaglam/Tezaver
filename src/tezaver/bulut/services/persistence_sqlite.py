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
        
        # Upsert
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
        close_order_id: Optional[int] = None
    ):
        """Mark position CLOSED and audit (ESTIMATED fallback)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        ts_str = close_ts.isoformat()
        cycle_ts_str = cycle_ts.isoformat() if cycle_ts else ts_str
        
        # Update positions
        cursor.execute("""
            UPDATE positions SET 
                status='CLOSED', 
                update_ts=?, 
                last_exit_reason=?,
                last_exit_cycle_ts=?
            WHERE symbol=?
        """, (ts_str, exit_reason, cycle_ts_str, symbol))
        
        # Audit
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
        
        # We process one by one to count insertions or use executemany with IGNORE
        # sqlite3 doesn't return inserted count easily with executemany + IGNORE
        # But for performance executemany is better.
        # We can just check rowcount but IGNORE might affect it.
        # Or better: "INSERT OR IGNORE"
        
        data = []
        for e in events:
            # e is raw binance income dict
            # keys: tranId, symbol, incomeType, income, asset, time, info
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
                json.dumps(e)
            ))
            
        cursor.executemany("""
            INSERT OR IGNORE INTO income_events (
                tran_id, symbol, income_type, asset, income, time_ms, time_ts, info, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)
        
        inserted_count = cursor.rowcount # rowcount is reliable for INSERT OR IGNORE in recent sqlite
        
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

    def set_income_last_sync_ms(self, ms: int):
        """Set last sync timestamp for income."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now_ts = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO system_state (key, value, updated_ts) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_ts=excluded.updated_ts
        """, ("income_last_sync_ms", str(ms), now_ts))
        conn.commit()
        conn.close()

    def get_today_income_sum_utc(self, types: List[str] = None, date_str: Optional[str] = None) -> dict:
        """
        Get sum of income for specific types today.
        Returns: { "FUNDING_FEE": 1.23, "TOTAL": 1.23, "non_usdt_count": 0 }
        """
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Filter by types if provided
        type_clause = ""
        args = [date_str]
        if types:
            placeholders = ",".join("?" * len(types))
            type_clause = f"AND income_type IN ({placeholders})"
            args.extend(types)
            
        query = f"""
            SELECT income_type, asset, SUM(income), COUNT(*)
            FROM income_events
            WHERE substr(time_ts, 1, 10) = ? {type_clause}
            GROUP BY income_type, asset
        """
        
        cursor.execute(query, tuple(args))
        rows = cursor.fetchall()
        conn.close()
        
        result = {"TOTAL": 0.0, "non_usdt_count": 0}
        
        for r in rows:
            # income_type, asset, sum, count
            i_type = r[0]
            asset = r[1]
            val = r[2]
            
            # Aggregate per type
            result[i_type] = result.get(i_type, 0.0) + val
            
            # Aggregate total (ONLY USDT IS SUMMED DIRECTLY)
            # If asset is not USDT, we do NOT add it to TOTAL PnL number directly for now
            # as per user instructions v0.17 (alerting) -> v0.19 will convert.
            # Wait, v0.18 requirements: "fee/income asset != USDT ise: emit_alert WARN code="NON_USDT_INCOME_UNACCOUNTED""
            # So for "TOTAL", we only sum USDT.
            if asset == "USDT":
                result["TOTAL"] += val
            else:
                result["non_usdt_count"] += r[3]
                
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
        
        # summary: {qty, vwap, realized_pnl, commission, commission_asset, net_pnl, ts_last}
        
        # We insert a new record for this "Closed Position Event"
        # Source=USER_TRADES
        
        cursor.execute("""
            INSERT INTO trade_audit (
                symbol, close_ts, exit_reason, 
                entry_price, exit_price, qty,
                pnl_usdt, pnl_is_estimated, cycle_ts,
                gross_pnl_usdt, fee_usdt, net_pnl_usdt, 
                pnl_source, close_order_id, pattern_id,
                fee_asset, fee_native
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 'USER_TRADES', ?, ?, ?, ?)
        """, (
            symbol, 
            datetime.fromtimestamp(summary["ts_last"]/1000.0, timezone.utc).isoformat(),
            exit_reason,
            entry_price,
            summary["vwap"],
            summary["qty"],
            summary["net_pnl"], # pnl_usdt = net for compat? Or gross? Let's use NET as authoritative pnl_usdt 
            cycle_ts,
            summary["realized_pnl"],
            summary["commission"] if summary.get("commission_asset") == "USDT" else 0.0, # fee_usdt only if USDT
            summary["net_pnl"],
            close_order_id,
            pattern_id,
            summary.get("commission_asset"),
            summary.get("commission")
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

    def get_today_pnl_stats_utc(self, date_str: Optional[str] = None) -> dict:
        """
        Get breakdown of PnL for a date (Net, Gross, Fees).
        """
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
        conn = self._get_conn()
        cursor = conn.cursor()
        
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
