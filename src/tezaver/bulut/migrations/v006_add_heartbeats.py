# Migration v006: Add Heartbeats
version = 6
description = "Create heartbeats table"

def apply(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS heartbeats (
            name TEXT PRIMARY KEY,
            last_ts TEXT,
            last_ms INTEGER,
            status TEXT,
            detail TEXT
        )
    """)

def dry_run():
    return ["CREATE TABLE IF NOT EXISTS heartbeats (...)"]
