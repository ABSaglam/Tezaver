import pandas as pd
import numpy as np
from pathlib import Path
import json

def load_and_standardize(file_path):
    """
    Yukler, Timestamp'i UTC ISO formatina cevirir, open/high/low/close/volume float yapar.
    Supports CSV and PARQUET.
    """
    path_obj = Path(file_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
        
    if path_obj.suffix == '.parquet':
        df = pd.read_parquet(path_obj)
    else:
        df = pd.read_csv(path_obj)
    
    # Kolon isimlerini kucuk harfe cevirip clean edelim
    df.columns = [c.strip().lower() for c in df.columns]
    
    # Zorunlu kolon kontrolu
    required = ['open', 'high', 'low', 'close', 'volume']
    # Timestamp/Date aliases
    if 'timestamp' in df.columns:
        pass
    elif 'date' in df.columns:
        df.rename(columns={'date': 'timestamp'}, inplace=True)
    elif 'datetime' in df.columns:
        df.rename(columns={'datetime': 'timestamp'}, inplace=True)
    else:
        raise ValueError(f"Missing timestamp/date column in {file_path}")
        
    for req in required:
        if req not in df.columns:
            raise ValueError(f"Missing required column: {req} in {file_path}")

    # Timestamp standardization
    # Eger numeric ise (ms veya s) ona gore cevir, string ise parse et
    try:
        if pd.api.types.is_numeric_dtype(df['timestamp']):
            if df['timestamp'].iloc[0] > 1e11: 
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            else:
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
        else:
            df['datetime'] = pd.to_datetime(df['timestamp'], utc=True)
    except Exception as e:
        raise ValueError(f"Timestamp split hatasi in {file_path}: {e}")

    # Sort
    df = df.sort_values('datetime').reset_index(drop=True)
    
    # Float conversion
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
        
    return df

def get_data_bundle(symbol="AVAXUSDT", base_path="/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/data/"):
    """
    Tum timeframe'leri yukler ve bir dictionary dondurur.
    Prioritizes: history_{tf}.parquet (Actual on disk) -> AVAXUSDT_{tf}.csv (User request)
    """
    timeframes = ['1w', '1d', '4h', '1h', '15m']
    bundle = {}
    base = Path(base_path)
    
    for tf in timeframes:
        # 1. Try Actual Disk Name key (history_1d.parquet)
        fpath_parquet_hist = base / f"history_{tf}.parquet"
        
        # 2. Try User Requested Name (AVAXUSDT_1d.csv)
        fpath_csv_user = base / f"{symbol}_{tf}.csv"
        
        # 3. Try fallback Parquet (AVAXUSDT_1d.parquet)
        fpath_parquet_user = base / f"{symbol}_{tf}.parquet"
        
        if fpath_parquet_hist.exists():
            bundle[tf] = load_and_standardize(fpath_parquet_hist)
        elif fpath_csv_user.exists():
            bundle[tf] = load_and_standardize(fpath_csv_user)
        elif fpath_parquet_user.exists():
            bundle[tf] = load_and_standardize(fpath_parquet_user)
        else:
            print(f"WARNING: Data for {tf} not found in {base}. Trying to proceed without it (might fail if critical).")
            # Create empty placeholder if needed, or skip
            continue
            
    return bundle

def save_json_rule(data, path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w') as f:
        json.dump(data, f, indent=4, sort_keys=True)

def verify_v17_row(row, schema_cols):
    keys = row.index if isinstance(row, pd.Series) else row.keys()
    if len(keys) != 26:
        return False, f"Column count mismatch: {len(keys)} != 26"
    for i, col in enumerate(schema_cols):
        if list(keys)[i] != col:
            return False, f"Column order/name mismatch at index {i}: {list(keys)[i]} != {col}"
    if isinstance(row, pd.Series):
        if row.isna().any():
            return False, "Row contains NaN values"
    return True, "OK"
