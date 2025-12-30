
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from tezaver.core.annotations import SniperAnnotationRepository, SniperStatus
from tezaver.ui.chart_area import load_history_data
import pandas as pd

def migrate():
    repo = SniperAnnotationRepository()
    # List all symbol dirs
    root = Path(".tezaver_matrix/foundry/annotations")
    if not root.exists():
        print("No annotations found.")
        return

from tezaver.core import coin_cell_paths

def migrate():
    repo = SniperAnnotationRepository()
    # List all symbol dirs
    root = Path(".tezaver_matrix/foundry/annotations")
    if not root.exists():
        print("No annotations found.")
        return

    count = 0
    updated = 0
    
    for sym_dir in root.iterdir():
        if not sym_dir.is_dir(): continue
        symbol = sym_dir.name
        
        for ann_file in sym_dir.glob("*.json"):
            tf = ann_file.stem
            anns = repo.load_all(symbol, tf)
            save_needed = False
            
            # Load DF History once per file
            df = None
            
            # Load Raw Rallies for Fallback Bars
            raw_map = {}
            try:
                if tf == "15m":
                    rp = coin_cell_paths.get_fast15_rallies_path(symbol)
                else:
                    rp = coin_cell_paths.get_time_labs_rallies_path(symbol, tf)
                
                if rp.exists():
                    rdf = pd.read_parquet(rp)
                    # Map event_id -> bars_to_peak
                    # Also handle _RVZ_ mismatch by stripping?
                    # Annotations usually have same ID now.
                    for _, row in rdf.iterrows():
                        raw_map[str(row['event_id'])] = int(row['bars_to_peak'])
            except Exception as e:
                print(f"Raw load error {symbol} {tf}: {e}")

            for ann in anns:
                # Criteria: APPROVED and (Modified Offsets or Label=REV) and Missing rev_gain
                is_revised = (ann.label == "REV") or (ann.exit_bar_offset is not None) or (ann.entry_bar_offset != 0)
                
                # Debug
                # print(f"Check {ann.event_id}: entry={ann.entry_bar_offset}, exit={ann.exit_bar_offset}, label={ann.label}, rev_gain={ann.rev_gain}")

                if is_revised and (ann.rev_gain is None):
                    # Need calc
                    if df is None:
                        # print(f"Loading history for {symbol} {tf}...")
                        df = load_history_data(symbol, tf)
                        if df is not None:
                            if 'open_time' in df.columns: df = df.set_index('open_time')
                            if df.index.tz is not None: df.index = df.index.tz_localize(None)

                    if df is not None:
                        try:
                            # Parse TS
                            parts = ann.event_id.split('_')
                            ts_val = int(parts[-1])
                            ts = pd.to_datetime(ts_val, unit='s')
                            
                            if ts in df.index:
                                start_pos = df.index.get_loc(ts)
                                if isinstance(start_pos, slice): start_pos = start_pos.start
                                
                                # Entry
                                entry_off = ann.entry_bar_offset or 0
                                p_entry = df.iloc[min(start_pos + entry_off, len(df)-1)]['open']
                                
                                # Exit
                                exit_off = ann.exit_bar_offset
                                if exit_off is None:
                                    # Fallback to bars_to_peak
                                    # Try exact ID match, then try constructing base ID if needed
                                    bars = raw_map.get(ann.event_id)
                                    if bars is None:
                                        # Try stripping _RVZ_ just in case old ID
                                        if "_RVZ_" in ann.event_id:
                                            base = ann.event_id.replace("_RVZ_", "_")
                                            bars = raw_map.get(base)
                                    
                                    if bars is not None:
                                        exit_off = bars
                                        print(f"  Fallback exit used: {bars}")
                                
                                if exit_off is not None:
                                    p_exit = df.iloc[min(start_pos + exit_off, len(df)-1)]['high']
                                    
                                    if p_entry > 0:
                                        gain = (p_exit - p_entry) / p_entry
                                        ann.rev_gain = gain
                                        save_needed = True
                                        updated += 1
                                        print(f"Updated {ann.event_id}: {gain*100:.1f}%")
                        except Exception as e:
                            print(f"Error {ann.event_id}: {e}")
                            
            if save_needed:
                repo.save_all(symbol, tf, anns)
                
    print(f"Migration Complete. Updated {updated} revisions.")

if __name__ == "__main__":
    migrate()
