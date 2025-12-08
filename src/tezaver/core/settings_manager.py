import json
import os
from pathlib import Path
from typing import Dict, Any

# Default locations and settings
SETTINGS_FILE = Path("data/user_settings.json")

DEFAULT_USER_SETTINGS = {
    "indicators": {
        "candles": {
            "up_color": "#089981",
            "down_color": "#F23645"
        },
        "rsi": {
            "enabled": True,
            "period": 11,
            "ema_period": 11,
            "source": "close",
            "color": "#7E57C2",
            "ema_color": "#FFC107"
        },
        "macd": {
            "enabled": True,
            "fast": 12,
            "slow": 26,
            "signal": 9,
            "color_tolerance": 0.0,  # 0-100%
            "macd_color": "#2962FF",
            "signal_color": "#FF9800",
            "hist_pos_inc_color": "#00E676",
            "hist_pos_dec_color": "#D500F9",
            "hist_neg_inc_color": "#FF1744",
            "hist_neg_dec_color": "#FFEA00"
        },
        "ema_fast": {
            "enabled": True,
            "period": 20,
            "color": "#2962FF"
        },
        "ema_slow": {
            "enabled": True,
            "period": 50,
            "color": "#FF9800"
        },
        "atr": {
            "enabled": False, # Default off to avoid clutter
            "period": 14,
            "multiplier": 2.0,
            "color": "#00BCD4"
        },
        "volume": {
            "enabled": True,
            "up_color": "#089981",
            "down_color": "#F23645"
        }
    }
}

class SettingsManager:
    """
    Manages loading and saving of user preferences (indicators, UI settings, etc.)
    to a persistent JSON file.
    """
    
    def __init__(self, settings_path: Path = SETTINGS_FILE):
        self.settings_path = settings_path
        self._ensure_data_dir()
        
    def _ensure_data_dir(self):
        """Ensures the directory for settings exists."""
        if not self.settings_path.parent.exists():
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            
    def load_settings(self) -> Dict[str, Any]:
        """Loads settings from JSON, merging with defaults and sanitizing colors."""
        if not self.settings_path.exists():
            return self.save_settings(DEFAULT_USER_SETTINGS)
            
        try:
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                user_settings = json.load(f)
                
            # Merge with defaults to ensure all keys exist
            merged = DEFAULT_USER_SETTINGS.copy()
            
            # Helper to validate hex color
            def is_valid_hex(s: str) -> bool:
                if not isinstance(s, str): return False
                if not s.startswith("#"): return False
                if len(s) not in (4, 7): return False
                try:
                    int(s[1:], 16)
                    return True
                except ValueError:
                    return False

            if 'indicators' in user_settings:
                # Update specific indicators with validation
                for key, val in user_settings['indicators'].items():
                    if key in merged['indicators']:
                        # Logic: Use user setting only if it is a valid value (simple merge)
                        current_default = merged['indicators'][key]
                        for subkey, subval in val.items():
                            # Color Sanitization
                            if "color" in subkey and not is_valid_hex(subval):
                                print(f"⚠️ Invalid color detected for {key}.{subkey}: {subval}. Reverting to default.")
                                continue # Skip updating this specific key, effectively keeping default
                            
                            # Apply safe value
                            current_default[subkey] = subval
                        
                        merged['indicators'][key] = current_default
                    else:
                        merged['indicators'][key] = val
            
            return merged
        except Exception as e:
            print(f"Error loading settings: {e}")
            return DEFAULT_USER_SETTINGS

    def save_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Saves dictionary to JSON file."""
        try:
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
            return settings
        except Exception as e:
            print(f"Error saving settings: {e}")
            return settings

# Singleton instance for easy access
settings_manager = SettingsManager()
