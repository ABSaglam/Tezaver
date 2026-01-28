import pandas as pd
import json
import os
import tqdm

def audit_data_depth():
    print("🔍 Starting Deep Data Audit (Target: 2023-01-01 to Present)")
    
    whitelist_path = "data/spot_whitelist_437.json"
    if not os.path.exists(whitelist_path):
        print("❌ Whitelist not found.")
        return

    with open(whitelist_path, "r") as f:
        whitelist = json.load(f)

    target_start = pd.Timestamp("2023-01-01")
    
    report_lines = []
    report_lines.append("# 📊 DETAYLI VERİ DENETİM RAPORU (2023+)\n")
    report_lines.append(f"**Hedef Başlangıç:** {target_start.date()}\n")
    report_lines.append(f"**Taranan Coin Sayısı:** {len(whitelist)}\n\n")
    report_lines.append("| Coin | 1D Başlangıç | 4H Başlangıç | 1H Başlangıç | 15m Başlangıç | Durum |\n")
    report_lines.append("|---|---|---|---|---|---|\n")

    issues_found = 0
    missing_files = []

    # Timeframes to check
    tfs = ['1d', '4h', '1h', '15m']
    
    for symbol in whitelist:
        row = f"| **{symbol}** |"
        symbol_issues = []
        
        base_path = f"coin_cells/{symbol}/data"
        if not os.path.exists(base_path):
            report_lines.append(f"| **{symbol}** | ❌ KLASÖR YOK | - | - | - | 🔴 EKSİK |\n")
            missing_files.append(symbol)
            continue
            
        for tf in tfs:
            file_path = f"{base_path}/history_{tf}.parquet"
            if not os.path.exists(file_path):
                row += f" ❌ Yok |"
                symbol_issues.append(f"{tf} Missing")
            else:
                try:
                    # Read only index to be fast? Parquet reading is fast.
                    # We can use columns to just read timestamp if possible, but reading all is safer for index check.
                    # To optimize, maybe read metadata? Pandas pyarrow engine allows meta read?
                    # Let's just read it, usually fast enough for 400 files.
                    df = pd.read_parquet(file_path, columns=['timestamp']) 
                    if df.empty:
                         row += f" ⚠️ Boş |"
                         symbol_issues.append(f"{tf} Empty")
                         continue

                    # Assumes sorted?
                    start_ts = df['timestamp'].min()
                    # end_ts = df['timestamp'].max()
                    
                    start_dt = pd.to_datetime(start_ts, unit='ms')
                    
                    # Check depth
                    is_shallow = False
                    if start_dt > target_start + pd.Timedelta(days=30): # 1 month buffer
                        is_shallow = True
                        
                    date_str = start_dt.strftime('%Y-%m-%d')
                    if is_shallow:
                        # Highlight shallow start
                        row += f" <font color='red'>{date_str}</font> |"
                        symbol_issues.append(f"{tf} Shallow")
                    else:
                        row += f" {date_str} |"
                        
                except Exception as e:
                    row += f" ⚠️ Hata |"
                    symbol_issues.append(f"{tf} Read Error")

        # Status Column
        if not symbol_issues:
            row += " 🟢 TAM |"
        else:
            issues_found += 1
            # Simplify issue text
            if len(symbol_issues) == 4 and "Missing" in symbol_issues[0]:
                 row += " 🔴 HİÇ YOK |"
            else:
                 row += f" 🟠 {' '.join([i.split()[0] for i in symbol_issues])} Eksik/Kısa |"
        
        report_lines.append(row + "\n")

    print(f"✅ Audit Complete. Found issues in {issues_found} coins.")
    
    with open("DATA_DEPTH_AUDIT_2023.md", "w") as f:
        f.writelines(report_lines)
    print("📄 Report saved to DATA_DEPTH_AUDIT_2023.md")

if __name__ == "__main__":
    audit_data_depth()
