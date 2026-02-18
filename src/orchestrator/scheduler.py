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
                        event_pattern=customer.google_calendar_event_pattern.strip(),
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


async def poll_slack_mentions():
    """Periodic job: check Slack channels for @mentions of the TAM."""
    from src.models.database import async_session
    from src.models.customer import Customer
    from src.models.integration import SlackMention
    from src.integrations.slack.client import SlackClient
    from src.integrations.base import IntegrationError

    logger.info("scheduler.slack_poll.start")

    async with async_session() as db:
        result = await db.execute(select(Customer))
        customers = result.scalars().all()

        for customer in customers:
            # Poll both internal and external channels
            channel_configs = []
            if customer.slack_internal_channel_id:
                channel_configs.append(("internal", customer.slack_internal_channel_id))
            if customer.slack_external_channel_id:
                channel_configs.append(("external", customer.slack_external_channel_id))

            for workspace, channel_id in channel_configs:
                try:
                    client = SlackClient(workspace)

                    # Get the last message_ts we've seen for this channel
                    last_mention = await db.execute(
                        select(SlackMention.message_ts)
                        .where(
                            SlackMention.channel_id == channel_id,
                            SlackMention.workspace == workspace,
                        )
                        .order_by(SlackMention.message_ts.desc())
                        .limit(1)
                    )
                    last_ts = last_mention.scalar_one_or_none()

                    # Fetch recent messages (since last seen, or last 20)
                    messages = await client.get_channel_history(
                        channel_id, limit=20, oldest=last_ts
                    )

                    # Look for messages mentioning the TAM
                    tam_user_id = customer.tam_slack_user_id
                    if not tam_user_id:
                        continue

                    mention_pattern = f"<@{tam_user_id}>"
                    new_count = 0

                    for msg in messages:
                        # Skip if this is the message we already have
                        if msg.get("ts") == last_ts:
                            continue

                        text = msg.get("text", "")
                        if mention_pattern not in text:
                            continue

                        # Check for duplicate
                        existing = await db.execute(
                            select(SlackMention.id).where(
                                SlackMention.message_ts == msg["ts"],
                                SlackMention.channel_id == channel_id,
                            )
                        )
                        if existing.scalar_one_or_none():
                            continue

                        # Get user info
                        user_name = None
                        try:
                            user_info = await client.get_user_info(msg.get("user", ""))
                            profile = user_info.get("profile", {})
                            user_name = profile.get("display_name") or profile.get("real_name") or user_info.get("name")
                        except Exception:
                            pass

                        # Get permalink
                        permalink = await client.get_permalink(channel_id, msg["ts"])

                        # Resolve <@USER_ID> patterns to real names
                        resolved_text = text
                        try:
                            resolved_text = await client.resolve_user_ids_in_text(text)
                        except Exception:
                            pass

                        # Get channel name
                        channel_name = None
                        try:
                            slack_api = await client._get_client()
                            ch_info = await slack_api.conversations_info(channel=channel_id)
                            channel_name = ch_info.get("channel", {}).get("name")
                        except Exception:
                            pass

                        mention = SlackMention(
                            customer_id=customer.id,
                            workspace=workspace,
                            channel_id=channel_id,
                            channel_name=channel_name,
                            message_ts=msg["ts"],
                            thread_ts=msg.get("thread_ts"),
                            user_id=msg.get("user", "unknown"),
                            user_name=user_name,
                            message_text=resolved_text[:4000],
                            permalink=permalink,
                        )
                        db.add(mention)
                        new_count += 1

                    if new_count:
                        logger.info(
                            "scheduler.slack_poll.new_mentions",
                            customer=customer.name,
                            workspace=workspace,
                            count=new_count,
                        )

                except IntegrationError as e:
                    logger.warning(
                        "scheduler.slack_poll.channel_failed",
                        customer=customer.name,
                        workspace=workspace,
                        error=str(e),
                    )
                except Exception as e:
                    logger.warning(
                        "scheduler.slack_poll.channel_error",
                        customer=customer.name,
                        workspace=workspace,
                        error=str(e),
                    )

        await db.commit()

    logger.info("scheduler.slack_poll.complete")


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

    # Poll Slack for @mentions every 2 minutes
    scheduler.add_job(
        poll_slack_mentions,
        "interval",
        minutes=2,
        id="poll_slack_mentions",
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
