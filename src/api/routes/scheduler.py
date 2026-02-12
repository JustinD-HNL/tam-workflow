"""Scheduler management API routes."""

import structlog
from fastapi import APIRouter, HTTPException

from src.orchestrator.scheduler import (
    check_integration_health,
    process_pending_workflows,
    scan_calendar_for_upcoming_meetings,
)

router = APIRouter()
logger = structlog.get_logger()

# Map of job names to their async handler functions
JOB_FUNCTIONS = {
    "scan_calendar_for_upcoming_meetings": scan_calendar_for_upcoming_meetings,
    "process_pending_workflows": process_pending_workflows,
    "check_integration_health": check_integration_health,
}


@router.post("/trigger/{job_name}")
async def trigger_job(job_name: str):
    """Manually trigger a scheduler job by name.

    Available jobs:
    - scan_calendar_for_upcoming_meetings: Scan Google Calendar for meetings in T-2 days
    - process_pending_workflows: Find and execute pending workflows
    - check_integration_health: Verify all integration connections are valid
    """
    job_fn = JOB_FUNCTIONS.get(job_name)
    if not job_fn:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown job: {job_name}. Available jobs: {list(JOB_FUNCTIONS.keys())}",
        )

    logger.info("scheduler.manual_trigger", job=job_name)
    try:
        await job_fn()
    except Exception as e:
        logger.error("scheduler.manual_trigger.failed", job=job_name, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Job '{job_name}' failed: {str(e)}",
        )

    return {"message": "Job triggered", "job": job_name}
