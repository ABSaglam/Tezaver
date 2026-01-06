
import sys
import os
import sqlite3
import pandas as pd
from datetime import datetime
import numpy as np

def analyze_seasonality():
    print("=" * 100)
    print(f"  RALLY MEVSİMSELLİK ANALİZİ (HAFTA 1-52) - MARKET GENİŞLİĞİ")
    print("=" * 100)

    # 1. Connect to SQLite
    db_path = "library/rallies.db"
    if not os.path.exists(db_path):
        print(f"❌ Veritabanı bulunamadı: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    
    # 2. Query Data - Get distinct days if possible, or just all events
    query = """
    SELECT 
        symbol,
        tier,
        event_time
    FROM rallies
    WHERE event_time >= datetime('now', '-1 year') -- Son 1 yıl
    """
    
    try:
        df = pd.read_sql_query(query, conn)
        conn.close()
    except Exception as e:
        print(f"❌ Sorgu hatası: {e}")
        return

    if df.empty:
        print("⚠️ Hiç veri bulunamadı.")
        return

    # 3. Process Data
    # Handle potentially mixed formats
    df['event_time'] = pd.to_datetime(df['event_time'], errors='coerce')
    
    # Drop rows with invalid dates
    if df['event_time'].isnull().any():
        df = df.dropna(subset=['event_time'])

    # Calculate Week Number
    df['week'] = df['event_time'].dt.isocalendar().week
    
    # Filter Tiers
    df['tier_group'] = df['tier'].apply(lambda x: '💎 PREMIUM' if x in ['DIAMOND', 'GOLD'] else 'Standard')

    # 4. Group by Week - COUNT UNIQUE SYMBOLS
    # Hangi hafta KAÇ FARKLI COIN trenddeydi?
    weekly_unique_coins = df.groupby('week')['symbol'].nunique()
    weekly_total_rallies = df.groupby('week')['symbol'].count()
    
    # Fill missing weeks
    all_weeks = pd.Series(0, index=range(1, 54))
    weekly_unique_coins = weekly_unique_coins.reindex(all_weeks.index, fill_value=0)

    # 5. Visualization (Text Based)
    max_unique = weekly_unique_coins.max()
    scale_factor = 50 / max_unique if max_unique > 0 else 1

    print(f"\n📊 TOPLAM VERİ: {len(df)} Ralli")
    print("-" * 100)
    print(f"{'Hafta':<6} | {'Coin Sy':<8} | {'Ralli Sy':<8} | {'Piyasa Genişliği':<50}")
    print("-" * 100)

    for week in range(1, 53):
        unique_count = int(weekly_unique_coins.get(week, 0))
        total_rallies = int(weekly_total_rallies.get(week, 0))
        
        # ASCII Bar based on UNIQUE COINS
        bar_len = int(unique_count * scale_factor)
        bar = "█" * bar_len
        
        # Highlight high breadth weeks
        note = ""
        if unique_count > weekly_unique_coins.mean() * 1.5:
            note = "🔥 MEGA BULL"
        elif unique_count < weekly_unique_coins.mean() * 0.5:
            note = "❄️ AYI"
            
        print(f"W {week:<4} | {unique_count:<8} | {total_rallies:<8} | {bar:<30} {note}")

    print("-" * 100)
    print(f"ℹ️ Açıklama: 'Coin Sy' o hafta en az 1 ralli yapmış FARKLI coin sayısıdır.")
    print("=" * 100)

if __name__ == "__main__":
    analyze_seasonality()
