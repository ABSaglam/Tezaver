#!/usr/bin/env python3
path = "/Users/alisaglam/TezaverMac/dna_mujde_audit_report_green_v3.md"
try:
    with open(path, "r") as f:
        lines = f.readlines()
    
    total_loss = 0
    for l in lines:
        if "|" not in l or "Loss" not in l or "Coin" in l: continue
        parts = l.split("|")
        if len(parts) >= 6:
            loss_str = parts[5].replace("Loss", "").strip()
            total_loss += int(loss_str)
            
    print(f"Toplam Diamond Kaybı: {total_loss}")
except Exception as e: print(e)
