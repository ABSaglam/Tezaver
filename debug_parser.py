
import pandas as pd
import os

def parse_check():
    date_str = "2026-01-27"
    report_path = "/Users/alisaglam/TezaverMac/refined_global_report_v16.md"
    
    month_map = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}
    dt = pd.Timestamp(date_str)
    search_header = f"{dt.day} {month_map[dt.month]} {dt.year}"
    print(f"Leafing for: '{search_header}'")
    
    with open(report_path, "r") as f:
        lines = f.readlines()
        
    found = False
    for line in lines:
        if "## 📅" in line:
            print(f"Header found: {line.strip()}")
            if search_header in line:
                print("MATCH!")
                found = True
    
    if not found:
        print("NO MATCH FOUND.")

parse_check()
