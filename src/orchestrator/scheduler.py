"""APScheduler setup for periodic tasks."""

from datetime import datetime, timedelta, timezone

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy import select

from src.config.settings import settings

logger = structlog.get_logger()

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the scheduler instance."""
    global _scheduler
    if _scheduler is None:
        # Use sync database URL for APScheduler's job store
        sync_db_url = settings.database_url.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://")
        # Fallback: if it's already a sync URL, use as-is
        if "asyncpg" not in sync_db_url:
            sync_db_url = settings.database_url.replace("postgresql+asyncpg", "postgresql")

        jobstores = {
            "default": SQLAlchemyJobStore(url=sync_db_url),
        }

        _scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 3600,
            },
        )
    return _scheduler


async def scan_calendar_for_upcoming_meetings():
    """Daily job: scan Google Calendar for meetings in T-2 days and trigger agenda generation."""
    from src.models.database import async_session
    from src.models.customer import Customer
    from src.models.workflow import Workflow, WorkflowType, WorkflowStatus
    from src.integrations.google import GoogleCalendarClient

    logger.info("scheduler.calendar_scan.start")

    try:
        calendar = GoogleCalendarClient()
        async with async_session() as db:
            # Get all customers
            result = await db.execute(select(Customer))
            customers = result.scalars().all()

            for customer in customers:
                if not customer.google_calendar_event_pattern:
                    continue

                try:
                    # Look for meetings in 2 days
                    meetings = await calendar.find_customer_meetings(
                        event_pattern=customer.google_calendar_event_pattern,
                        days_ahead=3,
                    )

                    target_date = datetime.now(timezone.utc) + timedelta(days=2)
                    target_date_str = target_date.strftime("%Y-%m-%d")

                    for meeting in meetings:
                        start = meeting.get("start", {})
                        meeting_date = start.get("dateTime", start.get("date", ""))
                        if meeting_date.startswith(target_date_str):
                            # Check if we already have a workflow for this meeting
                            existing = await db.execute(
                                select(Workflow).where(
                                    Workflow.customer_id == customer.id,
                                    Workflow.workflow_type == WorkflowType.AGENDA_GENERATION,
                                    Workflow.context["meeting_date"].astext == meeting_date,
                                )
                            )
                            if existing.scalar_one_or_none():
                                continue

                            # Create agenda generation workflow
                            workflow = Workflow(
                                workflow_type=WorkflowType.AGENDA_GENERATION,
                                status=WorkflowStatus.PENDING,
                                customer_id=customer.id,
                                context={
                                    "meeting_date": meeting_date,
                                    "calendar_event_id": meeting.get("id"),
                                    "meeting_summary": meeting.get("summary", ""),
                                },
                            )
                            db.add(workflow)
                            logger.info(
                                "scheduler.agenda_triggered",
                                customer=customer.name,
                                meeting_date=meeting_date,
                            )

                except Exception as e:
                    logger.error(
                        "scheduler.customer_scan_failed",
                        customer=customer.name,
                        error=str(e),
                    )

            await db.commit()

    except Exception as e:
        logger.error("scheduler.calendar_scan.failed", error=str(e))

    logger.info("scheduler.calendar_scan.complete")


async def check_integration_health():
    """Periodic job: verify all integration connections are still valid."""
    from src.models.database import async_session
    from src.models.integration import IntegrationCredential, IntegrationStatus

    logger.info("scheduler.health_check.start")

    async with async_session() as db:
        result = await db.execute(select(IntegrationCredential))
        creds = result.scalars().all()

        for cred in creds:
            if cred.status == IntegrationStatus.CONNECTED and cred.expires_at:
                if cred.expires_at < datetime.now(timezone.utc):
                    cred.status = IntegrationStatus.EXPIRED
                    logger.warning(
                        "scheduler.token_expired",
                        integration=cred.integration_type,
                    )

        await db.commit()

    logger.info("scheduler.health_check.complete")


async def process_pending_workflows():
    """Periodic job: find and execute pending workflows."""
    from src.models.database import async_session
    from src.models.workflow import Workflow, WorkflowStatus
    from src.orchestrator.workflows import execute_workflow

    logger.info("scheduler.process_workflows.start")

    async with async_session() as db:
        result = await db.execute(
            select(Workflow)
            .where(Workflow.status == WorkflowStatus.PENDING)
            .order_by(Workflow.created_at)
            .limit(5)
        )
        workflows = result.scalars().all()

        for workflow in workflows:
            try:
                await execute_workflow(workflow.id, db)
            except Exception as e:
                logger.error(
                    "scheduler.workflow_execution_failed",
                    workflow_id=str(workflow.id),
                    error=str(e),
                )

        await db.commit()

    logger.info("scheduler.process_workflows.complete")


def setup_scheduler():
    """Configure and start the scheduler with all jobs."""
    scheduler = get_scheduler()

    # Daily calendar scan at 8 AM
    scheduler.add_job(
        scan_calendar_for_upcoming_meetings,
        "cron",
        hour=8,
        minute=0,
        id="calendar_scan",
        replace_existing=True,
    )

    # Process pending workflows every 30 seconds
    scheduler.add_job(
        process_pending_workflows,
        "interval",
        seconds=30,
        id="process_workflows",
        replace_existing=True,
    )

    # Integration health check every hour
    scheduler.add_job(
        check_integration_health,
        "interval",
        hours=1,
        id="integration_health_check",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("scheduler.started", jobs=len(scheduler.get_jobs()))
    return scheduler
