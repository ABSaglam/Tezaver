
import pandas as pd

df = pd.read_parquet("/Users/alisaglam/TezaverMac/library/fast15_rallies/BTCUSDT/fast15_rallies.parquet")
# Set display options to avoid truncation
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
pd.set_option('display.max_colwidth', 50)

print(df[['event_time', 'future_max_gain_pct', 'scenario_label', 'narrative_tr']].tail(5))
