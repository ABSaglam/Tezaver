import pandas as pd
from tezaver.core import coin_cell_paths

path = coin_cell_paths.get_history_file("BTCUSDT", "1h")
if path.exists():
    df = pd.read_parquet(path)
    print("Columns:", df.columns.tolist())
    print("Index Type:", type(df.index))
    if not df.empty:
        print("First Row:", df.iloc[0])
else:
    print("File not found")
