
"""
Priority Manager
================
Central logic for sorting rallies based on User's Golden Rule.
Priority Order:
1.  15m diamond
2.  15m gold
3.  4h diamond
4.  1h diamond
5.  15m silver
6.  4h gold
7.  1h gold
8.  15m bronze
9.  4h silver
10. 1h silver
11. 4h bronze
12. 1h bronze
"""

def get_priority_rank(rally_data: dict) -> int:
    """
    Returns a rank integer (lower is better/higher priority).
    Unknown combinations get rank 99.
    """
    tf = rally_data.get('timeframe', '')
    tier = rally_data.get('tier', 'BRONZE')
    
    # Normalize inputs just in case
    tf = tf.lower().strip() if tf else ''
    tier = tier.upper().strip() if tier else 'BRONZE'
    
    # 1. 15m Diamond
    if tf == '15m' and tier == 'DIAMOND': return 1
    # 2. 15m Gold
    if tf == '15m' and tier == 'GOLD': return 2
    # 3. 4h Diamond
    if tf == '4h' and tier == 'DIAMOND': return 3
    # 4. 1h Diamond
    if tf == '1h' and tier == 'DIAMOND': return 4
    # 5. 15m Silver
    if tf == '15m' and tier == 'SILVER': return 5
    # 6. 4h Gold
    if tf == '4h' and tier == 'GOLD': return 6
    # 7. 1h Gold
    if tf == '1h' and tier == 'GOLD': return 7
    # 8. 15m Bronze
    if tf == '15m' and tier == 'BRONZE': return 8
    # 9. 4h Silver
    if tf == '4h' and tier == 'SILVER': return 9
    # 10. 1h Silver
    if tf == '1h' and tier == 'SILVER': return 10
    # 11. 4h Bronze
    if tf == '4h' and tier == 'BRONZE': return 11
    # 12. 1h Bronze
    if tf == '1h' and tier == 'BRONZE': return 12
    
    return 99

def sort_rallies_by_priority(rallies: list) -> list:
    """
    Sorts a list of rally dictionaries based on the Golden Rule.
    """
    # Sort by Rank (Ascending), then by Symbol (Alphabetical) as tie-breaker
    return sorted(rallies, key=lambda x: (get_priority_rank(x), x.get('symbol', '')))
