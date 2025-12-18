# Migration v003: Add Income Events & Alerts & Order Fills
version = 3
description = "Create alerts, order_fills, income_events tables"

def apply(cursor):
    # Alerts (v0.15)
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

    # Order Fills (v0.17)
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
    
    # Income Events (v0.18)
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

def dry_run():
    return [
        "CREATE TABLE IF NOT EXISTS alerts (...)",
        "CREATE TABLE IF NOT EXISTS order_fills (...)",
        "CREATE TABLE IF NOT EXISTS income_events (...)"
    ]
