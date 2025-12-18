# Migration v005: Add State Reducer Tables
version = 5
description = "Create applied_events and add update_ts to positions"

def apply(cursor):
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

def dry_run():
    return [
        "CREATE TABLE IF NOT EXISTS applied_events (...)",
        "ALTER TABLE positions ADD COLUMN last_update_ts_ms INTEGER"
    ]
