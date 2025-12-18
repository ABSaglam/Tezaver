from fastapi import APIRouter
from tezaver.bulut.app_backend import get_context

router = APIRouter()

@router.get("/status")
async def get_migration_status():
    """Get migration status (current vs pending)."""
    ctx = get_context()
    if not ctx: return {}
    
    # We use dry run to inspect pending
    report = ctx.migration_runner.run_pending(dry_run=True)
    return report

@router.post("/run")
async def run_migrations(dry_run: bool = False):
    """Run pending migrations."""
    ctx = get_context()
    if not ctx: return {}
    return ctx.migration_runner.run_pending(dry_run=dry_run)
