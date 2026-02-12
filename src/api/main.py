"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import auth, customers, approvals, dashboard, health, integrations, linear, resolve, slack, transcripts, workflows
from src.config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    from src.config.logging import setup_logging
    from src.models.database import engine
    from src.orchestrator.scheduler import setup_scheduler

    setup_logging()

    import structlog
    logger = structlog.get_logger()

    try:
        scheduler = setup_scheduler()
        logger.info("app.scheduler_started")
    except Exception as e:
        logger.warning("app.scheduler_failed", error=str(e))

    yield

    # Shutdown
    try:
        from src.orchestrator.scheduler import get_scheduler
        sched = get_scheduler()
        if sched.running:
            sched.shutdown(wait=False)
    except Exception:
        pass
    await engine.dispose()


app = FastAPI(
    title="TAM Workflow",
    description="Automated workflow system for Buildkite Technical Account Managers",
    version="0.1.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

# CORS — allow frontend on localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(customers.router, prefix="/api/customers", tags=["Customers"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["Approvals"])
app.include_router(transcripts.router, prefix="/api/transcripts", tags=["Transcripts"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["Workflows"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["Integrations"])
app.include_router(resolve.router, prefix="/api/integrations/resolve", tags=["Resolution"])
app.include_router(health.router, prefix="/api/health", tags=["Health"])
app.include_router(slack.router, prefix="/api/slack", tags=["Slack"])
app.include_router(linear.router, prefix="/api/linear", tags=["Linear"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])


@app.get("/health")
async def healthcheck():
    """Health check endpoint."""
    return {"status": "ok", "service": "tam-workflow"}
