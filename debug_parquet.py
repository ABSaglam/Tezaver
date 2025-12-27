
import pandas as pd
try:
    df = pd.read_parquet("coin_cells/BTCUSDT/data/features_15m.parquet")
    print("Columns:", df.columns.tolist())
    print("Head:\n", df.head())
except Exception as e:
    print(e)
