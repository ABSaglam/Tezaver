import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from tezaver.core.config import get_turkey_now

class SealManager:
    """
    Mühürleme Sistemi Yöneticisi (Seal Manager)
    
    Kritik sistem bileşenlerini "mühürleyerek" (kilitleyerek) kazara değişiklikleri önler.
    Mühürlenen öğelerin kaydını tutar ve mühür kırma işlemi için gerekli bilgileri sağlar.
    """
    
    def __init__(self, storage_path: str = "data/system_seals.json"):
        self.storage_path = Path(storage_path)
        self._seals: Dict[str, Any] = {}
        self._load()

    def _load(self):
        """Mühür verilerini diskten yükler."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    self._seals = json.load(f)
            except Exception as e:
                print(f"Error loading seals: {e}")
                self._seals = {}
        else:
            self._seals = {}

    def _save(self):
        """Mühür verilerini diske kaydeder."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self._seals, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving seals: {e}")

    def seal_item(self, key: str, reason: str, owner: str = "User") -> bool:
        """
        Bir öğeyi mühürler.
        
        Args:
            key: Öğenin benzersiz kimliği (örn. 'config_main').
            reason: Mühürleme nedeni.
            owner: Mühürleyen kişi/sistem.
        """
        if key in self._seals:
            return False # Already sealed
            
        now = get_turkey_now()
        self._seals[key] = {
            "sealed_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": now.timestamp(),
            "reason": reason,
            "owner": owner
        }
        self._save()
        return True

    def unseal_item(self, key: str) -> bool:
        """Bir öğenin mührünü kırar (siler)."""
        if key in self._seals:
            del self._seals[key]
            self._save()
            return True
        return False

    def is_sealed(self, key: str) -> bool:
        """Bir öğenin mühürlü olup olmadığını kontrol eder."""
        return key in self._seals

    def get_seal_info(self, key: str) -> Optional[Dict[str, Any]]:
        """Mühür detaylarını döndürür."""
        return self._seals.get(key)

    def get_all_seals(self) -> Dict[str, Any]:
        """Tüm mühürlü öğeleri döndürür."""
        return self._seals

# Global instance
seal_manager = SealManager()
