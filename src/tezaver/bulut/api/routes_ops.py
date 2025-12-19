# Tezaver Bulut - Ops API Routes
"""
Operations API: Status, Alerts, Incidents.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional

from tezaver.bulut.core.context import get_context
from tezaver.bulut.schemas.system_status_v1 import SystemStatusV1

router = APIRouter(tags=["ops"])

class IncidentExportRequest(BaseModel):
    reason: str

@router.get("/status", response_model=SystemStatusV1)
async def get_system_status():
    """Get aggregated system status."""
    ctx = get_context()
    return ctx.status_service.get_status(ctx)

@router.get("/alerts")
async def get_alerts(limit: int = 50):
    """Get recent system alerts."""
    ctx = get_context()
    alerts = ctx.persistence.get_latest_alerts(limit)
    return {"alerts": alerts}


@router.post("/ping")
async def ops_ping():
    """Simple ping for auth testing."""
    return {"ok": True, "msg": "pong"}

@router.post("/incident/export")
async def export_incident_bundle(req: IncidentExportRequest, background_tasks: BackgroundTasks):
    """
    Trigger incident bundle export.
    Returns path to zip (or job id in future).
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


@router.get("/tests/report")
async def get_test_report():
    """
    Get test report summary from latest JUnit XML.
    READ-ONLY, no auth required.
    """
    from tezaver.bulut.ui.pages.test_report import get_test_report as _get_report
    return _get_report()

