# Tezaver Bulut - Fault Lab API Routes
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel

from tezaver.bulut.core.fault_lab_service import FaultLabService
# Dependency injection placeholder (in prod use proper DI)
# For now we assume a global or request-state provider exists in `main.py` 
# or we import a singleton if architected that way. 
# We'll expect request.app.state.fault_lab_service

router = APIRouter(prefix="/fault", tags=["Fault Lab"])

class ProfileModel(BaseModel):
    id: str
    name: str
    description: str

class RunModel(BaseModel):
    id: str
    profile_id: str
    started_ts: str
    result: str
    notes: str
    scenario_name: str

class ActivateRequest(BaseModel):
    profile_id: str

def get_fault_service(request):
    return request.app.state.fault_lab_service

@router.get("/profiles", response_model=List[ProfileModel])
async def list_profiles(request: Request):
    svc: FaultLabService = request.app.state.fault_lab_service
    # Convert core objects to Pydantic models (implicit)
    return svc.list_profiles()

@router.post("/activate")
async def activate_profile(req: ActivateRequest, request: Request):
    svc: FaultLabService = request.app.state.fault_lab_service
    success = svc.activate_profile(req.profile_id)
    if not success:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"status": "ok", "active_profile": req.profile_id}

@router.post("/deactivate")
async def deactivate_profile(request: Request):
    svc: FaultLabService = request.app.state.fault_lab_service
    svc.deactivate()
    return {"status": "ok"}

@router.get("/runs", response_model=List[RunModel])
async def list_runs(request: Request, limit: int = 20):
    svc: FaultLabService = request.app.state.fault_lab_service
    return svc.get_runs(limit=limit)

@router.get("/active")
async def get_active_profile(request: Request):
    svc: FaultLabService = request.app.state.fault_lab_service
    return {"active_profile_id": svc.get_active_profile()}
