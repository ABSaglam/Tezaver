# Tezaver Bulut - Ops API Routes
"""
Operations API: Status, Alerts, Incidents.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional

from tezaver.bulut.core.context import get_context
from tezaver.bulut.schemas.system_status_v1 import SystemStatusV1

router = APIRouter(tags=["Ops"])

class IncidentExportRequest(BaseModel):
    reason: str

@router.get("/status", response_model=SystemStatusV1, summary="TR System Status")
async def get_system_status():
    """
    Get aggregated system status.
    
    TR Açıklama:
    Tüm sistem bileşenlerinin (trade, data, memory, vb.) özet sağlık durumunu döndürür.
    """
    ctx = get_context()
    return ctx.status_service.get_status(ctx)

@router.get("/alerts", summary="TR Get Alerts")
async def get_alerts(limit: int = 50):
    """
    Get recent system alerts.
    
    TR Açıklama:
    Sistem tarafından üretilen son alarmları (INFO/WARN/ERROR) listeler.
    """
    ctx = get_context()
    alerts = ctx.persistence.get_latest_alerts(limit)
    return {"alerts": alerts}


@router.post("/ping", summary="TR Auth Ping")
async def ops_ping():
    """
    Simple ping for auth testing.
    
    TR Açıklama:
    OpsAuth token'ın geçerliliğini test etmek için kullanılan basit ping endpoint'i.
    
    Güvenlik:
    - OpsAuth gerektirir (POST işlemi olduğu için middleware yakalar).
    """
    return {"ok": True, "msg": "pong"}

@router.post("/incident/export", summary="TR Export Incident Bundle")
async def export_incident_bundle(req: IncidentExportRequest, background_tasks: BackgroundTasks):
    """
    Trigger incident bundle export.
    Returns path to zip (or job id in future).
    
    TR Açıklama:
    Manuel olarak bir 'Incident' paketi oluşturur. Logları, DB snapshot'ını ve durumu paketler.
    
    Güvenlik:
    - OpsAuth gerektirir.
    """
    ctx = get_context()
    
    # We run this synchronously for now to return path, 
    # but for large logs/db it should be background.
    # Given request, let's just do it.
    try:
        zip_path = ctx.incident_bundle.create_bundle(ctx, req.reason)
        return {"status": "ok", "path": zip_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tests/report", summary="TR Test Report")
async def get_test_report():
    """
    Get test report summary from latest JUnit XML.
    READ-ONLY, no auth required.
    
    TR Açıklama:
    Son çalıştırılan testlerin sonuç özetini (Pass/Fail) döndürür.
    """
    from tezaver.bulut.ui.pages.test_report import get_test_report as _get_report
    return _get_report()

