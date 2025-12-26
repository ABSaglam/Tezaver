"""
Foundry Configuration Service
=============================

Manages the "Policy" (Anayasa) of the Foundry.
Loads rules from `foundry_policy.json`.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional

POLICY_PATH = Path(".tezaver_matrix/foundry/foundry_policy.json")

DEFAULT_POLICY = {
  "version": "1.1",
  "comment": "Foundry Policy (Dökümhane Anayasası)",
  "qc_rules": {
    "description": "Kalite Kontrol (QC) Kapısı Kuralları",
    "min_score": 60,
    "min_score_desc": "Bir revizyonun geçmesi için gereken minimum puan (0-100).",
    "strict_mode": True,
    "strict_mode_desc": "Açık ise, herhangi bir kırmızı hata (FAIL) durumunda puan yüksek olsa bile reddet.",
    "mandatory_checks": ["QC-010", "QC-040", "QC-050"],
    "mandatory_checks_desc": "Bu kontrollerin başarısız olması durumunda kesinlikle reddedilir."
  },
  "packaging_rules": {
    "description": "Paketleme ve Sevkiyat Kuralları",
    "allowed_tiers": ["DIAMOND", "GOLD", "SILVER", "BRONZE"],
    "allowed_tiers_desc": "Hangi kalite sınıflarının (Tier) paketlenmesine izin verilir?",
    "max_bundles_per_coin": 5,
    "max_bundles_per_coin_desc": "Bir coinin aynı TF'de en fazla kaç versiyonu olabilir?",
    "naming_convention": "STANDARD_V1"
  },
  "alchemist_rules": {
    "description": "Simyacı (Arketip Keşfi) Kuralları",
    "min_cohort_size": 3,
    "min_cohort_size_desc": "Analiz için gereken minimum paket sayısı.",
    "default_k": 3,
    "default_k_desc": "Varsayılan küme (arketip) sayısı.",
    "features": ["gain", "duration", "volatility"],
    "features_desc": "Kümelemede kullanılacak öznitelikler (DNA)."
  }
}

class ConfigurationService:
    def __init__(self, policy_path: Path = POLICY_PATH):
        self.policy_path = policy_path
        self._policy = self._load_policy()

    def _load_policy(self) -> Dict[str, Any]:
        """Load policy from disk or create default."""
        if not self.policy_path.exists():
            self._ensure_dir()
            with open(self.policy_path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_POLICY, f, indent=2)
            return DEFAULT_POLICY
        
        try:
            with open(self.policy_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to load policy: {e}. Using Default.")
            return DEFAULT_POLICY

    def _ensure_dir(self):
        self.policy_path.parent.mkdir(parents=True, exist_ok=True)

    def get_qc_rules(self) -> Dict[str, Any]:
        return self._policy.get("qc_rules", DEFAULT_POLICY["qc_rules"])

    def get_packaging_rules(self) -> Dict[str, Any]:
        return self._policy.get("packaging_rules", DEFAULT_POLICY["packaging_rules"])
        
    def get_alchemist_rules(self) -> Dict[str, Any]:
        return self._policy.get("alchemist_rules", DEFAULT_POLICY["alchemist_rules"])

    def get_version(self) -> str:
        return self._policy.get("version", "1.0")
        
    def save_policy(self, new_policy: Dict[str, Any]):
        """Update and save policy."""
        self._policy = new_policy
        self._ensure_dir()
        with open(self.policy_path, "w", encoding="utf-8") as f:
            json.dump(new_policy, f, indent=2)
