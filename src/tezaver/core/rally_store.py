"""
Rally Store (Unified SQLite Storage)
=====================================
"Tek Kayıt, Tek Yer" (Single Record, Single Place)

This module implements the unified storage engine using SQLite.
It stores the entire lifecycle of a rally in a single row with JSON blobs.

Schema:
    id (PK): TEXT (BTCUSDT_15m_D_12345)
    symbol: TEXT
    timeframe: TEXT
    tier: TEXT
    event_time: TIMESTAMP
    
    raw_data: JSON (Scanner output)
    rev_data: JSON (Annotation)
    molder_data: JSON (Archetype)
    alchemy_data: JSON (Cipher)
    
    created_at: TIMESTAMP
    updated_at: TIMESTAMP
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
import pandas as pd

from tezaver.core.logging_utils import get_logger
from tezaver.core import coin_cell_paths

# Register adapters for Pandas Timestamp
def adapt_timestamp(ts):
    return ts.isoformat()

sqlite3.register_adapter(pd.Timestamp, adapt_timestamp)
sqlite3.register_adapter(datetime, adapt_timestamp)

logger = get_logger(__name__)

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"

class RallyStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize the database schema if it doesn't exist."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Enable WAL mode for concurrency
        cursor.execute("PRAGMA journal_mode=WAL;")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rallies (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                tier TEXT,
                event_time TIMESTAMP,
                
                raw_data TEXT,
                rev_data TEXT,
                molder_data TEXT,
                alchemy_data TEXT,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Indices for fast filtering
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sym_tf ON rallies(symbol, timeframe);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tier ON rallies(tier);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_time ON rallies(event_time);")
        
        conn.commit()
        conn.close()

    def upsert_rally(self, rally_id: str, data: Dict[str, Any], layer: str = 'raw'):
        """
        Insert or Update a rally record.
        
        Args:
            rally_id: Unique ID
            data: Dictionary of data to save
            layer: Which layer to update ('raw', 'rev', 'molder', 'alchemy')
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        json_str = json.dumps(data, default=str)
        now = datetime.now()
        
        # Check existence
        cursor.execute("SELECT id FROM rallies WHERE id = ?", (rally_id,))
        exists = cursor.fetchone()
        
        if not exists:
            # Create new record (usually from Scanner/Raw layer)
            if layer != 'raw':
                # Rare case: annotating a non-existent raw rally? 
                # Should we allow it? Yes, creating a placeholder.
                pass
            
            # Extract meta from data if available, else placeholders
            symbol = data.get('symbol', 'UNKNOWN')
            timeframe = data.get('timeframe', 'UNKNOWN')
            tier = data.get('rally_grade') or data.get('tier', 'UNKNOWN')
            event_time = data.get('event_time', now)
            
            col_name = f"{layer}_data"
            
            sql = f"""
                INSERT INTO rallies (id, symbol, timeframe, tier, event_time, {col_name}, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(sql, (rally_id, symbol, timeframe, tier, event_time, json_str, now, now))
            
        else:
            # Update existing
            col_name = f"{layer}_data"
            sql = f"""
                UPDATE rallies 
                SET {col_name} = ?, updated_at = ?
                WHERE id = ?
            """
            cursor.execute(sql, (json_str, now, rally_id))
            
        conn.commit()
        conn.close()

    def get_rally(self, rally_id: str) -> Optional[Dict[str, Any]]:
        """Get full rally document by ID."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM rallies WHERE id = ?", (rally_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return self._row_to_dict(row)
        return None

    def list_rallies(self, symbol: str = None, timeframe: str = None, tier: str = None, status: str = None, limit: int = 5000) -> List[Dict[str, Any]]:
        """Query rallies with filters."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM rallies WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if timeframe:
            query += " AND timeframe = ?"
            params.append(timeframe)
        if tier:
            query += " AND tier = ?"
            params.append(tier)
        
        # JSON Filter Hack (SAFE for our schema)
        if status:
            # We assume standard JSON encoding: "status": "APPROVED"
            # Note: Spacing might vary if manually edited, but standard json.dumps uses consistent spacing.
            # To be safer, we can just look for the value if we trust the context, or use LIKE logic.
            # rev_data LIKE '%"status": "APPROVED"%'
            query += " AND rev_data LIKE ?"
            params.append(f'%"{status}"%')
            
        query += " ORDER BY event_time DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_dict(r) for r in rows]

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert SQLite row to unified dict."""
        res = dict(row)
        # Parse JSON fields
        for field in ['raw_data', 'rev_data', 'molder_data', 'alchemy_data']:
            if res[field]:
                try:
                    res[field] = json.loads(res[field])
                except:
                    res[field] = {}
            else:
                res[field] = None
        return res

    def delete_all(self):
        """Dangerous: Wipe DB."""
        conn = self._get_conn()
        conn.execute("DELETE FROM rallies")
        conn.commit()
        conn.close()
