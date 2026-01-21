import json
import sys
import os
import subprocess

# List of B-series coins to process (excluding already reported ones if needed, but for the full report let's do all B's or just the remaining ones? 
# The user wants "tüm b ler bitene kadar sorma". I will process the remaining ones and then compile a report for all B's if possible, or just the remaining ones + links to previous.
# To be robust, let's process the remaining ones first.

remaining_coins = [
    "BIFIUSDT", "BIGTIMEUSDT", "BIOUSDT", "BLURUSDT", "BMTUSDT", 
    "BNBUSDT", "BNSOLUSDT", "BNTUSDT", "BOMEUSDT", "BONKUSDT", 
    "BREVUSDT", "BROCCOLI714USDT", "BTCUSDT", "BTTCUSDT"
]

# We will also fetch data for previously processed B coins to include in the final report for completeness
# processed_coins = ["BABYUSDT", "BANANAS31USDT", "BANANAUSDT", "BANDUSDT", "BANKUSDT", "BARDUSDT", "BEAMXUSDT", "BELUSDT", "BERAUSDT", "BFUSDUSDT", "BICOUSDT"]
# BFUSDUSDT failed, so we skip or mark as failed.

all_b_coins = [
    "BABYUSDT", "BANANAS31USDT", "BANANAUSDT", "BANDUSDT", "BANKUSDT", 
    "BARDUSDT", "BEAMXUSDT", "BELUSDT", "BERAUSDT", "BICOUSDT",
    "BIFIUSDT", "BIGTIMEUSDT", "BIOUSDT", "BLURUSDT", "BMTUSDT", 
    "BNBUSDT", "BNSOLUSDT", "BNTUSDT", "BOMEUSDT", "BONKUSDT", 
    "BREVUSDT", "BROCCOLI714USDT", "BTCUSDT", "BTTCUSDT"
]

report_file = "B_SERISI_OZET_RAPORU.md"

def get_dgs_data(symbol):
    try:
        # We assume forge_golden_key has been run for all of these in the mass production step.
        # We just need to run compare_dgs to get the stats.
        result = subprocess.run(
            ["venv/bin/python", "scripts/compare_dgs.py", symbol], 
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return None
        
        # Parse the last line which contains the JSON
        lines = result.stdout.strip().split('\n')
        json_line = lines[-1]
        data = json.loads(json_line)
        return data
    except Exception as e:
        return None

with open(report_file, "w") as f:
    f.write("# 🚇 AYAŞ TÜNELİ v4: B SERİSİ TOPLU RAPORU\n\n")
    f.write(f"**Rapor Tarihi:** 2026-01-21\n")
    f.write("**Kapsam:** B Harfi ile Başlayan Tüm Koinler\n\n")
    f.write("---\n\n")

    for symbol in all_b_coins:
        print(f"Processing {symbol}...")
        data = get_dgs_data(symbol)
        
        if not data or "error" in data:
            f.write(f"## ❌ {symbol}\n\n")
            f.write("*Veri alınamadı veya üretim hatası (Saf DNA bulunamamış olabilir).*\n\n")
            f.write("---\n\n")
            continue

        # Format Data
        total = data.get('total_counts', {})
        t_avg = data.get('total_avgs', {})
        v4 = data.get('v4_counts', {})
        v4_avg = data.get('v4_avgs', {})
        pct = data.get('pct', {})

        f.write(f"## 🦅 {symbol}\n\n")
        
        f.write("**1. Tarihi Ralli Verimliliği (Tüm Geçmiş):**\n\n")
        f.write(f"    💎 Diamond: {total.get('DIAMOND',0)} ralli (Ort. %{t_avg.get('DIAMOND',0)})\n")
        f.write(f"    🥇 Gold: {total.get('GOLD',0)} ralli (Ort. %{t_avg.get('GOLD',0)})\n")
        f.write(f"    🥈 Silver: {total.get('SILVER',0)} ralli (Ort. %{t_avg.get('SILVER',0)})\n")
        f.write(f"    Toplam: {sum(total.values())} Ralli\n\n")

        f.write("**2. Ayaş Tüneli v4 \"Saf\" Yakalamalar:**\n\n")
        f.write(f"    💎 Diamond: {v4.get('DIAMOND',0)} yakalanan (Ort. %{v4_avg.get('DIAMOND',0)})\n")
        f.write(f"    🥇 Gold: {v4.get('GOLD',0)} yakalanan (Ort. %{v4_avg.get('GOLD',0)})\n")
        f.write(f"    🥈 Silver: {v4.get('SILVER',0)} yakalanan (Ort. %{v4_avg.get('SILVER',0)})\n")
        f.write(f"    📊 Genel Sonuç: {sum(total.values())} ralliden {sum(v4.values())} tanesi (%{pct.get('TOTAL',0)})\n\n")
        
        f.write("**📢 Yorum (Yakalama Oranları):**\n\n")
        f.write(f"    💎 Diamond: {total.get('DIAMOND',0)} ralliden {v4.get('DIAMOND',0)} tanesi yakalandı (Yakalanma Oranı: %{pct.get('DIAMOND',0)})\n")
        f.write(f"    🥇 Gold: {total.get('GOLD',0)} ralliden {v4.get('GOLD',0)} tanesi yakalandı (Yakalanma Oranı: %{pct.get('GOLD',0)})\n")
        f.write(f"    🥈 Silver: {total.get('SILVER',0)} Silver ralliden {v4.get('SILVER',0)} tanesi tünelden geçti (Yakalanma Oranı: %{pct.get('SILVER',0)})\n\n")

        f.write(f"**🚀 GENEL SKOR:** {symbol} tarihindeki tüm rallilerin %{pct.get('TOTAL',0)}'i v4 protokolümüzle mühürlendi.\n\n")
        f.write("---\n\n")
