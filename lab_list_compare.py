
import pandas as pd
from datetime import timedelta

def compare_lists():
    # 1. System List (From lab_diamond_report output)
    system_list = [
        "2023-12-08 08:00:00",
        "2024-11-09 04:45:00",
        "2024-11-22 00:30:00",
        "2024-12-20 11:45:00",
        "2025-02-03 01:45:00",
        "2025-03-01 15:45:00",
        "2025-03-02 15:45:00", # Close to user's 15:15
        "2025-10-10 21:15:00"
    ]
    
    # 2. User List
    user_list = [
        "2025-10-10 21:15:00",
        "2025-03-02 15:15:00",
        "2025-03-02 06:15:00",
        "2024-11-22 10:00:00",
        "2024-11-09 15:00:00"
    ]
    
    print("🔍 COMPARISON REPORT")
    print("===================")
    
    sys_set = [pd.to_datetime(x) for x in system_list]
    user_set = [pd.to_datetime(x) for x in user_list]
    
    matches = []
    
    print(f"{'USER TIME':<25} | {'SYSTEM MATCH':<25} | {'DIFF (Hours)'}")
    print("-" * 70)
    
    for u in user_set:
        # Find closest system match
        closest = min(sys_set, key=lambda s: abs(s - u))
        diff = closest - u
        diff_hours = diff.total_seconds() / 3600
        
        status = "EXACT MATCH" if diff_hours == 0 else f"{diff_hours:+.1f}h"
        print(f"{str(u):<25} | {str(closest):<25} | {status}")
        
    print("\nINTERPRETATION:")
    print("1. 21:15 is EXACT match.")
    print("2. 15:00 vs 04:45 -> -10.25h diff? (UTC vs User Local?)")
    print("3. 10:00 vs 00:30 -> -9.5h diff?")
    
if __name__ == "__main__":
    compare_lists()
