import re
from collections import Counter

report_path = 'analysis/ayas_tuneli_2y_120h_rapor.md'

def list_negative_diamond_stars():
    with open(report_path, 'r') as f:
        content = f.read()
    
    # Negative Diamond pattern like: SYMBOL(-DIAMOND:-35%)
    pattern = r'(\w+)\(-DIAMOND:'
    matches = re.findall(pattern, content)
    
    counts = Counter(matches)
    
    print(f"--- Negative Diamond Performers ---")
    if not matches:
        print("No Negative Diamond events found.")
        return
        
    sorted_stars = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    for symbol, count in sorted_stars:
        print(f"{symbol}: {count} times")
        
    return sorted_stars

if __name__ == "__main__":
    list_negative_diamond_stars()
