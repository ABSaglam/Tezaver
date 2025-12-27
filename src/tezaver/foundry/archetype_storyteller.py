"""
Foundry Archetype Storyteller (The Alchemist: Distillation Phase)
=================================================================

Responsible for looking at raw Cluster Stats and assigning a 
"Soul" (Name/Description) to the Archetype.
"""

from typing import Dict, Any

class ArchetypeStoryteller:
    def tell_story(self, centroid: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a narrative for a cluster centroid.
        
        Args:
            centroid: Dict with avg_gain, avg_duration, avg_vol
            
        Returns:
            Dict with 'label', 'description', 'risk_profile'
        """
        gain = centroid['avg_gain']
        dur = centroid['avg_duration']
        vol = centroid['avg_vol']
        
        # 1. Determine Identity (The Name)
        label = "Unknown Entity"
        desc = "A mysterious pattern with undefined characteristics."
        risk = "Medium"
        
        # Logic Tree for Naming
        # Logic Tree for Naming
        # Calibrated based on ADA 15m data (Avg Vol 0.6, Window 400)
        
        if dur < 150: 
            # Short Duration (Early peak)
            if gain > 5:
                label = "⚡ The Flash (Explosive Pop)"
                desc = "Fast, violent breakout that peaks quickly."
                risk = "High"
            else:
                label = "🌱 The Wick (Quick Spike)"
                desc = "Short-lived spike, often retracing quickly."
                risk = "Low"
        else:
            # Long Duration (Sustained move)
            if vol > 0.8:
                label = "🎢 The Rollercoaster (Volatile Trend)"
                desc = "Long lasting but very shaky ride. High volatility."
                risk = "High"
            else:
                label = "🚂 The Steam Engine (Steady Grind)"
                desc = "Low volatility, consistent uptrend. The most desirable 'compounder'."
                risk = "Low"
        if gain > 15:
            label += " (Titan)"
            desc += " Be aware: This is a massive outlier move."
            
        return {
            "label": label,
            "description": desc,
            "risk_profile": risk,
            "stat_summary": f"Avg Gain: {gain:.1f}% | Duration: {int(dur)} bars | Vol: {vol:.2f}"
        }
