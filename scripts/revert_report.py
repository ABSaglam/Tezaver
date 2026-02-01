
import os

def revert_report():
    report_path = '/Users/alisaglam/TezaverMac/refined_global_report_v16.md'
    
    with open(report_path, 'r') as f:
        lines = f.readlines()
        
    # Find start of the bad block "17 Ocak"
    start_idx = -1
    for i, line in enumerate(lines):
        if "## 📅 17 Ocak 2026" in line:
            start_idx = i
            break
            
    # Find start of "28 Ocak"
    end_idx = -1
    for i, line in enumerate(lines):
        if "## 📅 28 Ocak 2026" in line:
            end_idx = i
            break
            
    if start_idx != -1 and end_idx != -1:
        print(f"Removing lines {start_idx} to {end_idx}")
        # Restore the placeholder for 21 Jan just so there isn't a huge gap, 
        # or just leave it empty. Let's look at what was there before.
        # It was just 21 Jan.
        
        placeholder = [
            "\n",
            "## 📅 21 Ocak 2026 (Geçen: 1 Kalan: 1)\n",
            "| NO | SYM | MAX | CLOSE | TIME | SIG | TREND | POS | ANG | VAL | P | P-21 | BAR | NEXT | R-Rib | Vrsi | V100 | V21 | V-Mom | VBoy | V-Ch | V-Avg |\n",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n",
            "| 1 | TUSDUSDT | +0.0% | <font color='red'>-0.0%</font> | 02:00 | | 🟢🟢 | 🟡 | <font color='green'>**+6.3**</font> | 💚 | +0.0% | 0.0% | 1 | <font color='red'>-0.0%</font> | 🟢 | 4.7 | <font color='gray'>3.3</font> | 3.3 | 1.0x | <font color='green'>**10.0**</font> | +93.3% | +-22.5% |\n",
            "\n"
        ]
        
        new_lines = lines[:start_idx] + placeholder + lines[end_idx:]
        
        with open(report_path, 'w') as f:
            f.writelines(new_lines)
        print("Revert complete.")
    else:
        print("Could not find markers to revert.")

if __name__ == '__main__':
    revert_report()
