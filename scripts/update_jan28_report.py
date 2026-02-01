
import os

REPORT_PATH = '/Users/alisaglam/TezaverMac/refined_global_report_v16.md'
SNIPPET_PATH = '/Users/alisaglam/TezaverMac/jan28_snippet.md'

def update_report():
    with open(REPORT_PATH, 'r') as f:
        report_lines = f.readlines()
        
    with open(SNIPPET_PATH, 'r') as f:
        snippet_lines = f.readlines()
        
    # Find Jan 28 start
    start_idx = -1
    for i, line in enumerate(report_lines):
        if "## 📅 28 Ocak 2026" in line:
            start_idx = i
            break
            
    if start_idx == -1:
        print("Could not find Jan 28 section in report.")
        return

    # In this case, Jan 28 is the LAST entry, so we replace from start_idx to end
    print(f"Replacing from line {start_idx} to end.")
    
    # Keep everything before, append new snippet
    new_report_lines = report_lines[:start_idx] + snippet_lines
    
    # Ensure newline at EOF
    if new_report_lines and not new_report_lines[-1].endswith('\n'):
        new_report_lines[-1] += '\n'
        
    with open(REPORT_PATH, 'w') as f:
        f.writelines(new_report_lines)
        
    print("Successfully updated Jan 28 section.")

if __name__ == "__main__":
    update_report()
