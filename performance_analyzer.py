import pandas as pd
import numpy as np
from pathlib import Path

def analyze_performance():
    df = pd.read_csv("Reports/DNA_JAN2026_DAILY_REPORT.csv")
    
    print("--- PERFORMANCE BY TIER ---")
    tier_perf = df.groupby("Matched Tier").agg({
        "Hit >=10%?": [lambda x: (x=="YES").sum(), "count"],
        "Max %": "mean"
    })
    tier_perf.columns = ["Hits", "Total", "Avg Max %"]
    tier_perf["Hit Rate %"] = (tier_perf["Hits"] / tier_perf["Total"]) * 100
    print(tier_perf)
    
    print("\n--- TOP SYMBOLS BY HIT RATE ---")
    coin_perf = df.groupby("Symbol").agg({
        "Hit >=10%?": [lambda x: (x=="YES").sum(), "count"],
        "Max %": "mean"
    })
    coin_perf.columns = ["Hits", "Total", "Avg Max %"]
    coin_perf["Hit Rate %"] = (coin_perf["Hits"] / coin_perf["Total"]) * 100
    print(coin_perf.sort_values(by="Hits", ascending=False).head(10))

if __name__ == "__main__":
    analyze_performance()
