from fastapi import APIRouter
from tezaver.bulut.core.context import get_context

router = APIRouter(prefix="/config", tags=["Config"])

@router.post("/snapshot", summary="TR Manual Config Snapshot")
async def take_snapshot():
    """
    Manual config snapshot.
    
    TR Açıklama:
    Mevcut konfigürasyonun anlık görüntüsünü (snapshot) veritabanına kaydeder.
    
    Güvenlik:
    - OpsAuth gerektirir.
    """
    ctx = get_context()
    if not ctx: return {}
    return ctx.drift_guard.check_and_record(source="MANUAL")

@router.get("/snapshot/latest", summary="TR Latest Config Snapshot")
async def get_latest_snapshot():
    """
    Get latest snapshot info.
    
    TR Açıklama:
    Alınan son konfigürasyon snapshot'ını döndürür.
    """
    ctx = get_context()
    if not ctx: return {}
    return ctx.persistence.get_latest_config_snapshot()
