"""
ONY Auto-Approver Daemon
========================

Scans rally libraries (Fast15, TimeLabs) and automatically creates 
APPROVED annotations for any event that doesn't have one.

Philosophy: "Default Approve" - Trust the scanner.
"""

import pandas as pd
from pathlib import Path
from typing import List, Optional
import datetime
import logging

# Import existing models (Now in core path)
from tezaver.core.annotations import (
    SniperAnnotation,
    SniperAnnotationRepository,
    SniperStatus,
    SniperLabel
)
from tezaver.core import coin_cell_paths

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OnyAutoApprover")


class OnyAutoApprover:
    def __init__(self, base_dir: Path = None):
        # We ignore base_dir if passed, as we use the default foundry path
        self.repo = SniperAnnotationRepository()

    def _load_events(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Load events from parquet files using coin_cell_paths."""
        if timeframe == "15m":
            path = coin_cell_paths.get_fast15_rallies_path(symbol)
        else:
            path = coin_cell_paths.get_time_labs_rallies_path(symbol, timeframe)

        if not path.exists():
            return pd.DataFrame()

        try:
            df = pd.read_parquet(path)
            logger.info(f"Loaded {len(df)} events for {symbol} {timeframe}.")
            return df
        except Exception as e:
            logger.error(f"Failed to read parquet {path}: {e}")
            return pd.DataFrame()

    def process_symbol(self, symbol: str, timeframe: str) -> int:
        """
        Scan events for symbol/tf and creating missing annotations.
        Returns count of created annotations.
        """
        # 1. Load Events
        df_events = self._load_events(symbol, timeframe)
        if df_events.empty:
            return 0
        
        # DEBUG
        logger.info(f"Processing {symbol} {timeframe}: {len(df_events)} events found in library.")

        # Ensure event_id exists
        if 'event_id' not in df_events.columns:
            logger.error(f"Skipping {symbol} {timeframe}: No 'event_id' found in Parquet. Please re-run scanner.")
            return 0

        # 2. Load Existing Annotations
        existing_anns = self.repo.load_all(symbol, timeframe)
        existing_event_ids = {ann.event_id for ann in existing_anns}

        # 3. Process Events
        created_count = 0
        updated_count = 0
        
        # Map existing by ID for easy access
        existing_map = {ann.event_id: ann for ann in existing_anns}
        
        # List of annotations to save (mixed new and updated)
        anns_to_save = []
        
        # Keep track of IDs we've processed from df to avoid duplicates if any
        processed_ids = set()

        for _, row in df_events.iterrows():
            eid = row['event_id']
            if eid in processed_ids:
                continue
            processed_ids.add(eid)
            
            if eid not in existing_map:
                # CASE 1: New Event -> Create APPROVED
                ann = SniperAnnotation(
                    symbol=symbol,
                    timeframe=timeframe,
                    event_id=eid,
                    entry_bar_offset=0,
                    note="Auto-Approved by System",
                    status="APPROVED",
                    label="GOOD",
                    snap_algo_version="AUTO_APPROVER_V1"
                )
                anns_to_save.append(ann)
                created_count += 1
            else:
                # CASE 2: Existing Event -> Check if PENDING
                ann = existing_map[eid]
                if ann.status == "PENDING":
                    ann.status = "APPROVED"
                    ann.note += " [Auto-Approved]"
                    anns_to_save.append(ann)
                    updated_count += 1

        # 4. Save
        if anns_to_save:
            # We need to merge anns_to_save with the REST of existing_anns that weren't touched?
            # Or just save everything.
            # Easiest is to reconstruct the full list.
            # logic:
            # Start with existing_anns.
            # For every ann in anns_to_save:
            #   if it was new, append it.
            #   if it was update, it's already in existing_anns object reference (mutated).
            # So actually, since I mutated objects in `existing_map` (references), `existing_anns` is already updated!
            # I just need to append the NEW ones to `existing_anns`.
            
            # Separate new vs updated for saving logic clarity
            # actually anns_to_save contains mixed.
            
            final_list = list(existing_anns)
            for ann in anns_to_save:
                if ann not in final_list:
                    final_list.append(ann)
            
            self.repo.save_all(symbol, timeframe, final_list)
            
            if created_count > 0 or updated_count > 0:
                logger.info(f"[{symbol} {timeframe}] Auto-Approve: Created {created_count}, Upgraded {updated_count}.")

        return created_count + updated_count

    def scan_all_coins(self):
        """Scan all coins present in coin_cells."""
        coin_cells_dir = self.base_dir / "coin_cells"
        if not coin_cells_dir.exists():
            logger.error("coin_cells directory not found.")
            return

        symbols = [p.name for p in coin_cells_dir.iterdir() if p.is_dir()]
        timeframes = ["15m", "1h", "4h"]
        
        total_created = 0
        for sym in symbols:
            for tf in timeframes:
                total_created += self.process_symbol(sym, tf)
        
        logger.info(f"=== Auto-Approver Finished. Total Created: {total_created} ===")

if __name__ == "__main__":
    approver = OnyAutoApprover()
    approver.scan_all_coins()
