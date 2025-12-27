
import sys
import pandas as pd
from pathlib import Path

# Add src to path
sys.path.append(str(Path.cwd() / "src"))

from tezaver.foundry.clustering_service import ClusteringService
from tezaver.foundry.bundle_index import scan_bundles

print("Scanning bundles...")
df = scan_bundles()
print(f"Found {len(df)} bundles in total.")

if df.empty:
    print("No bundles found. Exiting.")
    sys.exit()

service = ClusteringService()

# Filter for a symbol that exists
symbol = "ADAUSDT"
cohort = df[df['symbol'] == symbol]
print(f"Cohort ({symbol}): {len(cohort)} bundles.")

success_count = 0
fail_count = 0

for idx, row in cohort.iterrows():
    b_dir = Path(row['bundle_dir'])
    # Try extract
    try:
        f = service._extract_features(b_dir)
        if f:
            success_count += 1
            # print(f"Valid: {row['bundle_id']}")
        else:
            fail_count += 1
            print(f"INVALID: {row['bundle_id']} - _extract_features returned None")
            # Dig deeper
            pw_path = b_dir / "price_window.parquet"
            if not pw_path.exists():
                print(f"  -> Reason: price_window.parquet missing")
            else:
                try:
                    pw_df = pd.read_parquet(pw_path)
                    if pw_df.empty:
                        print(f"  -> Reason: price_window.parquet is empty")
                    elif 'close' not in pw_df.columns:
                        print(f"  -> Reason: 'close' column missing in {pw_df.columns}")
                    else:
                        print(f"  -> Reason: Unknown logic failure. Rows: {len(pw_df)}")
                except Exception as e:
                     print(f"  -> Reason: Read Error: {e}")

    except Exception as e:
        print(f"CRASH: {row['bundle_id']} - {e}")

print(f"Summary: {success_count} Valid, {fail_count} Invalid.")
