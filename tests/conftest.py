"""Shared test fixtures for the tam-workflow test suite.

Uses SQLite with aiosqlite for fast, isolated testing without requiring PostgreSQL.
Handles PostgreSQL-specific type translation (UUID -> String, JSONB -> JSON).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Patch settings before any app imports so we control the encryption key and DB URL.
# This prevents the real Settings() from trying to connect to PostgreSQL.
_test_encryption_key = "dGVzdC1lbmNyeXB0aW9uLWtleS0xMjM0NTY3ODkwYWI="  # base64 placeholder

_mock_settings_values = {
    "database_url": "sqlite+aiosqlite:///:memory:",
    "encryption_key": "",  # Will be overridden per-test where needed
    "anthropic_api_key": "",
    "google_client_id": "",
    "google_client_secret": "",
    "slack_internal_client_id": "",
    "slack_internal_client_secret": "",
    "slack_internal_app_token": "",
    "slack_external_client_id": "",
    "slack_external_client_secret": "",
    "slack_external_app_token": "",
    "linear_client_id": "",
    "linear_client_secret": "",
    "notion_client_id": "",
    "notion_client_secret": "",
    "oauth_redirect_base_url": "http://localhost:8000",
    "frontend_url": "http://localhost:3000",
    "log_level": "WARNING",
    "debug": False,
}


# ---------------------------------------------------------------------------
# Compile-time type translation: make PostgreSQL types work on SQLite
# ---------------------------------------------------------------------------
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ARRAY
from sqlalchemy.ext.compiler import compiles


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(type_, compiler, **kw):
    return "JSON"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_engine():
    """Create an in-memory SQLite async engine with all tables."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Import all models so Base.metadata knows about them
    import src.models  # noqa: F401
    from src.models.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_engine):
    """Provide a database session that rolls back after each test."""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def sample_customer(db):
    """Insert and return a sample customer for use in tests."""
    from src.models.customer import Customer, Cadence, HealthStatus

    customer = Customer(
        id=uuid.uuid4(),
        name="Test Corp",
        slug="test-corp",
        cadence=Cadence.WEEKLY,
        health_status=HealthStatus.GREEN,
    )
    db.add(customer)
    await db.flush()
    return customer


@pytest_asyncio.fixture
async def sample_approval_item(db, sample_customer):
    """Insert and return a sample approval item in DRAFT status."""
    from src.models.workflow import ApprovalItem, ApprovalItemType, ApprovalStatus

    item = ApprovalItem(
        id=uuid.uuid4(),
        item_type=ApprovalItemType.AGENDA,
        status=ApprovalStatus.DRAFT,
        title="Test Agenda for Test Corp",
        content="# Agenda\n\n- Topic 1\n- Topic 2",
        customer_id=sample_customer.id,
    )
    db.add(item)
    await db.flush()
    return item


@pytest_asyncio.fixture
async def app(db_engine):
    """Create a test FastAPI app with the DB dependency overridden to use SQLite."""
    from src.api.main import app as _app
    from src.models.database import get_db

    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    _app.dependency_overrides[get_db] = override_get_db
    yield _app
    _app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app):
    """Provide an async HTTP test client for the FastAPI app."""
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
        yield c
