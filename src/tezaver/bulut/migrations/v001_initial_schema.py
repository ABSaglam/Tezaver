# Migration v001: Initial Schema
version = 1
description = "Initialize positions, trade_plans, system_state"

def apply(cursor):
    # Positions
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
            open_ts TEXT,
            update_ts TEXT,
            side TEXT,
            sl_order_id TEXT,
            tp_order_id TEXT,
            sl_client_order_id TEXT,
            tp_client_order_id TEXT,
            protective_status TEXT
        )
    """)
    
    # Trade Plans
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
    
    # System State
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_ts TEXT
        )
    """)

def dry_run():
    return [
        "CREATE TABLE IF NOT EXISTS positions (...)",
        "CREATE TABLE IF NOT EXISTS trade_plans (...)",
        "CREATE TABLE IF NOT EXISTS system_state (...)"
    ]
