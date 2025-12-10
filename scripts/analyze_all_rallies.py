
import pandas as pd
import glob
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath("src"))

def analyze_all_rallies():
    # 1. Load Data
    files = glob.glob("library/fast15_rallies/*/fast15_rallies.parquet")
    if not files:
        print("❌ Hiç rally dosyası bulunamadı!")
        return

    dfs = []
    for f in files:
        try:
            df = pd.read_parquet(f)
            # Add symbol column if missing (extracted from path)
            symbol = f.split('/')[-2]
            df['symbol'] = symbol
            dfs.append(df)
        except Exception as e:
            print(f"Hata: {f} okunamadı: {e}")

    if not dfs:
        print("❌ Veri okunamadı.")
        return

    all_rallies = pd.concat(dfs, ignore_index=True)
    
    print("=== TÜM PİYASA RALLY ANALİZİ (MULTI-COIN) ===\n")
    print(f"📊 Toplam Rally: {len(all_rallies)}")
    print(f"📊 Taranan Coinler: {all_rallies['symbol'].nunique()}")
    
    # 2. Grade Distribution
    print("\n💎 GRADE DAĞILIMI:")
    grade_counts = all_rallies['rally_grade'].value_counts()
    for grade in ['💎 Diamond', '🥇 Gold', '🥈 Silver', '🥉 Bronze']:
        count = grade_counts.get(grade, 0)
        pct = (count / len(all_rallies) * 100) if len(all_rallies) > 0 else 0
        print(f"  {grade}: {count} ({pct:.1f}%)")

    # 3. Tier Statistics (Pattern Discovery)
    print("\n🔬 TIER PATTERN ANALİZİ (Ortak Özellikler):")
    
    tier_stats = all_rallies.groupby('rally_grade').agg({
        'future_max_gain_pct': 'mean',
        'quality_score': 'mean',
        'momentum_score': 'mean',
        'bars_to_peak': 'mean',
        'retention_10_pct': 'mean'
    }).reindex(['💎 Diamond', '🥇 Gold', '🥈 Silver', '🥉 Bronze']) # Force order
    
    for tier, row in tier_stats.iterrows():
        if pd.isna(row['future_max_gain_pct']): continue # Skip if no rallies
        
        print(f"\n{tier}:")
        print(f"  Ort. Kazanç: %{row['future_max_gain_pct']*100:.1f}")
        print(f"  Ort. Kalite: {row['quality_score']:.1f}/100")
        print(f"  Ort. Momentum: {row['momentum_score']:.2f}/1.0")
        print(f"  Ort. Süre: {row['bars_to_peak']:.1f} bar")
        
        # Specific pattern finding logic
        tier_df = all_rallies[all_rallies['rally_grade'] == tier]
        if not tier_df.empty:
            avg_rsi = tier_df['rsi_15m'].mean() if 'rsi_15m' in tier_df.columns else 0
            # Just printing if available
            if avg_rsi > 0: print(f"  Ort. RSI (Başlangıç): {avg_rsi:.1f}")

    # 4. Top Performing Rallies (The "Cream of the Crop")
    print("\n🏆 PİYASANIN EN İYİLERİ (Diamond & Gold):")
    high_tier = all_rallies[all_rallies['rally_grade'].isin(['💎 Diamond', '🥇 Gold'])]
    
    if high_tier.empty:
        print("  Henüz Diamond veya Gold rally tespit edilmedi.")
        # Show top Scored Silvers instead
        print("\n🥈 EN İYİ SİLVER RALLY'LER:")
        high_tier = all_rallies[all_rallies['rally_grade'] == '🥈 Silver']
    
    top_rallies = high_tier.nlargest(10, 'overall_score')
    
    for idx, row in top_rallies.iterrows():
        date_str = pd.to_datetime(row['event_time']).strftime('%Y-%m-%d %H:%M')
        print(f"  {row['rally_grade']} {row['symbol']} ({date_str})")
        print(f"     Kazanç: %{row['future_max_gain_pct']*100:.1f} | Kalite: {row['quality_score']:.0f} | Mom: {row['momentum_score']:.2f}")

if __name__ == "__main__":
    analyze_all_rallies()

