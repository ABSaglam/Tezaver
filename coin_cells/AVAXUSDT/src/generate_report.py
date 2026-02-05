import pandas as pd
from datetime import datetime
import sys

# Load Data
try:
    df = pd.read_csv("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/output/avax_kader_v1/runs/initial_learn/reports/AVAX_NET_ADAY_REPORT_ELITE.csv")
except:
    print("CSV Not Found")
    sys.exit(1)

# Sort by Date
df['Date'] = pd.to_datetime(df['Date'])
df = df.sort_values('Date')

# Report Header
report = f"""# 🦅 AVAX KADER MOTORU (ELITE MODE) - NET ADAY RAPORU
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Context: Elite Optimization (Strict ADX + P10-P90)

## 💎 ELITE ADAYLAR (Count: {len(df)})

| NO | DATE | SYM | TIER | DECISION | SCORE | ADX | ATR | VRSI | V-MOM | E-GAP | DRIFT | HIT_10 | MAX% |
|----|------|-----|------|----------|-------|-----|-----|------|-------|-------|-------|--------|------|
"""

# Rows
for i, row in df.iterrows():
    # Formatting
    date_str = row['Date'].strftime('%Y-%m-%d')
    sym = row['Symbol']
    tier = "💎" if "DIAMOND" in row['Tier'] else "🥇"
    decision = "NET_ADAY"
    score = f"{row['Score']:.2f}"
    adx = f"{row['ADX']:.1f}"
    atr = f"{row['ATR_Norm']:.3f}"
    vrsi = f"{row['Vrsi']:.1f}"
    vmom = f"{row['V-Mom']:.2f}"
    egap = f"{row['Energy_Gap']:.1f}"
    drift = f"{row['Drift_Factor']:.2f}"
    
    # Hit_10 Logic
    hit = row['Hit_10']
    hit_icon = "✅ YES" if hit == "YES" else "❌ NO"
    
    # Max Excursion Color
    max_exc = row['Max_Excursion']
    max_str = f"+{max_exc:.2f}%"
    if max_exc >= 10.0:
        max_str = f"<font color='green'><b>{max_str}</b></font>"
    elif max_exc > 0:
        max_str = f"<font color='lightgreen'>{max_str}</font>"
    else:
        max_str = f"<font color='red'>{max_str}</font>"

    line = f"| {i+1} | {date_str} | {sym} | {tier} | {decision} | {score} | {adx} | {atr} | {vrsi} | {vmom} | {egap} | {drift} | {hit_icon} | {max_str} |\n"
    report += line

report += """
### LEGEND
*   **DRIFT:** Rolling DNA'dan sapma (Düşük iyidir)
*   **E-GAP:** Energy Gap (Fiyat RSI - Hacim RSI)
*   **HIT_10:** Ertesi 24s içinde %10+ gördü mü? (Kader Teyidi)
"""

print(report)

with open("/Users/alisaglam/TezaverMac/coin_cells/AVAXUSDT/output/avax_kader_v1/runs/initial_learn/reports/AVAX_ELITE_RAPORU.md", "w") as f:
    f.write(report)
