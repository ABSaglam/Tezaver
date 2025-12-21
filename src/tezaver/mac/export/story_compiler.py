import pandas as pd
from typing import List, Dict, Any

class StoryCompiler:
    """
    Compiles detailed stories into higher timeframe summaries.
    MACX-2040
    """
    
    def compile_summaries(self, stories: List[Dict[str, Any]], target_tf: str) -> List[Dict[str, Any]]:
        """
        Groups stories by the target timeframe and produces deterministic summaries.
        TR: Hikayeleri hedef TF'ye göre gruplar ve deterministik özetler üretir.
        """
        if not stories:
            return []
            
        # Strategy: Group by target TF window
        # For v0, we just return a sample summary per window
        df = pd.DataFrame([
            {
                "time_utc": pd.Timestamp(s['entry']['event_time_utc']),
                "gain": s['target']['expected_gain_pct'],
                "symbol": s['symbol']
            } for s in stories
        ])
        
        # Floor to target TF
        df['group_time'] = df['time_utc'].dt.floor(target_tf.replace('H', 'h').replace('h', 'h'))
        
        summaries = []
        for timeptr, group in df.groupby('group_time'):
            summaries.append({
                "time_utc": timeptr.isoformat(),
                "story_count": len(group),
                "avg_expected_gain": round(group['gain'].mean(), 4),
                "max_expected_gain": round(group['gain'].max(), 4),
                "timeframe": target_tf
            })
            
        return summaries
