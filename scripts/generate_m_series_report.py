import json
import sys
import os
import subprocess

all_m_coins = [
    "MAGICUSDT", "MANAUSDT", "MANTAUSDT", "MASKUSDT", "MAVUSDT", 
    "MBLUSDT", "MBOXUSDT", "MDTUSDT", "MEMEUSDT", "METISUSDT", 
    "METUSDT", "MEUSDT", "MINAUSDT", "MIRAUSDT", "MITOUSDT", 
    "MLNUSDT", "MMTUSDT", "MORPHOUSDT", "MOVEUSDT", "MOVRUSDT", 
    "MTLUSDT", "MUBARAKUSDT"
]

report_file = "M_SERISI_OZET_RAPORU.md"

def get_dgs_data(symbol):
    try:
        result = subprocess.run(
            ["venv/bin/python", "scripts/compare_dgs.py", symbol], 
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return None
        
        lines = result.stdout.strip().split('\n')
        json_line = lines[-1]
        data = json.loads(json_line)
        return data
    except Exception as e:
        return None

with open(report_file, "w") as f:
    f.write("# 🚇 AYAŞ TÜNELİ v4: M SERİSİ TOPLU RAPORU\n\n")
    f.write(f"**Rapor Tarihi:** 2026-01-21\n")
    f.write("**Kapsam:** M Harfi ile Başlayan Tüm Koinler\n\n")
    f.write("---\n\n")

    for symbol in all_m_coins:
        print(f"Processing {symbol}...")
        data = get_dgs_data(symbol)
        
        if not data or "error" in data:
            f.write(f"## ❌ {symbol}\n\n")
            f.write("*Veri alınamadı veya üretim hatası (Saf DNA bulunamamış olabilir).*\n\n")
            f.write("---\n\n")
            continue

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
