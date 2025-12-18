# Migration v007: Add Config Snapshots
version = 7
description = "Create config_snapshots table"

def apply(cursor):
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

def dry_run():
    return ["CREATE TABLE IF NOT EXISTS config_snapshots (...)"]
