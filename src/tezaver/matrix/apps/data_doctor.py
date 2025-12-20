import argparse
import sys
import os
import json
import time
from datetime import datetime

from tezaver.matrix.core.bars import Bar
from tezaver.matrix.core.timeframes import parse_timeframe_to_seconds
from tezaver.matrix.core.data_quality import validate_bars
from tezaver.matrix.core.fingerprint import fingerprint_file

def main():
    parser = argparse.ArgumentParser(description="Matrix Data Doctor")
    parser.add_argument("--path", required=True, help="Path to bars.json")
    parser.add_argument("--timeframe", required=True, help="15m, 1h, 4h")
    parser.add_argument("--home", help="Override TEZAVER_MATRIX_HOME")
    
    args = parser.parse_args()
    
    # 1. Setup
    fpath = args.path
    if not os.path.exists(fpath):
        print(f"File not found: {fpath}")
        sys.exit(2)
        
    home = args.home or os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix")
    report_dir = os.path.join(home, "data_reports")
    os.makedirs(report_dir, exist_ok=True)
    
    # 2. Parse & Validate
    try:
        tf_seconds = parse_timeframe_to_seconds(args.timeframe)
        
        with open(fpath, "r", encoding="utf-8") as f:
            raw_bars = json.load(f)
            
        bars = []
        for b in raw_bars:
            # Enforce is_closed presence roughly here or rely on Bar init?
            # Prompt says: "is_closed yoksa default True kabul etme; yoksa hata"
            if 'is_closed' not in b:
                raise ValueError("Bar missing 'is_closed' field")
            
            # Convert JSON seconds to internal MS if needed
            # Prompt said bars.json is epoch seconds. Internal Bar is ms.
            b_copy = b.copy()
            b_copy['ts'] = int(b['ts'] * 1000)
            
            bars.append(Bar(**b_copy))
            
        report = validate_bars(bars, tf_seconds)
        fp = fingerprint_file(fpath)
        
        # 3. Report Payload
        ts_now = datetime.now().isoformat()
        report_id = f"report_{args.timeframe}_{int(time.time())}"
        
        payload = {
            "report_id": report_id,
            "created_ts": ts_now,
            "timeframe": args.timeframe,
            "tf_seconds": tf_seconds,
            "count": len(bars),
            "first_ts": bars[0].ts if bars else None,
            "last_ts": bars[-1].ts if bars else None,
            "fingerprint": fp,
            "ok": report.ok,
            "issues": report.issues,
            "stats": report.stats
        }
        
        # 4. Save
        r_path = os.path.join(report_dir, f"{report_id}.json")
        l_path = os.path.join(report_dir, "latest.json")
        
        with open(r_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            
        # Write copy to latest.json
        with open(l_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            
        # 5. Output
        status = "OK" if report.ok else "FAIL"
        print(f"[{status}] Data Doctor Check Complete")
        print(f"Stats: {report.stats}")
        print(f"Report: {l_path}")
        
        if not report.ok:
            sys.exit(2)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main()
