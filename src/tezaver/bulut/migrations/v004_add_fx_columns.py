# Migration v004: Add FX Columns & Rates
version = 4
description = "Create fx_rates and add FX columns to income/audit"

def apply(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fx_rates (
            asset TEXT PRIMARY KEY,
            quote TEXT,
            rate REAL,
            source TEXT,
            updated_ts TEXT
        )
    """)

    # Income Columns
    for col in ["income_usdt REAL", "fx_rate REAL", "fx_source TEXT"]:
        try: cursor.execute(f"ALTER TABLE income_events ADD COLUMN {col}")
        except: pass

    # Trade Audit Columns (v0.17/0.19)
    try: cursor.execute("ALTER TABLE trade_audit ADD COLUMN fee_usdt REAL")
    except: pass
    
    try: cursor.execute("ALTER TABLE trade_audit ADD COLUMN fee_fx_rate REAL")
    except: pass
    
    try: cursor.execute("ALTER TABLE trade_audit ADD COLUMN fee_fx_source TEXT")
    except: pass

def dry_run():
    return [
        "CREATE TABLE IF NOT EXISTS fx_rates (...)",
        "ALTER TABLE income_events ADD COLUMN income_usdt/fx_rate/source",
        "ALTER TABLE trade_audit ADD COLUMN fee_usdt/fee_fx_rate/source"
    ]
