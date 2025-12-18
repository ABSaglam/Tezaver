# Migration v002: Add Trade Audit
version = 2
description = "Create trade_audit table and add exit columns to positions"

def apply(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_audit (
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
    
    # Idempotent Add Columns
    try:
        cursor.execute("ALTER TABLE positions ADD COLUMN last_exit_reason TEXT")
    except: pass
    
    try:
        cursor.execute("ALTER TABLE positions ADD COLUMN last_exit_cycle_ts TEXT")
    except: pass

def dry_run():
    return [
        "CREATE TABLE IF NOT EXISTS trade_audit (...)",
        "ALTER TABLE positions ADD COLUMN last_exit_reason TEXT",
        "ALTER TABLE positions ADD COLUMN last_exit_cycle_ts TEXT"
    ]
