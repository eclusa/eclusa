import pytest
import asyncpg
from alembic.config import Config
from alembic.command import upgrade
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def pg_container():
    """Real PG17 instance with pgvector + pg_search extensions (paradedb image)."""
    with PostgresContainer("paradedb/paradedb:latest") as pg:
        yield pg


@pytest.fixture(scope="session")
def db_url(pg_container) -> str:
    """Sync connection URL for Alembic — normalized to bare postgresql:// scheme."""
    url = pg_container.get_connection_url()
    # testcontainers may return postgresql+psycopg2:// or postgresql:// — normalize
    if "postgresql+psycopg2://" in url:
        url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    return url


@pytest.fixture(scope="session", autouse=True)
def apply_migrations(pg_container, db_url):
    """Run all Alembic migrations against the test container."""
    alembic_cfg = Config("alembic.ini")
    # Override the URL from alembic.ini with the test container's URL
    # Convert to async driver URL for env.py
    async_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    alembic_cfg.set_main_option("sqlalchemy.url", async_url)
    upgrade(alembic_cfg, "head")


@pytest.fixture
async def conn(pg_container) -> asyncpg.Connection:
    """Per-test asyncpg connection to the test database."""
    # Get sync URL from testcontainers and convert to plain postgresql:// for asyncpg
    url = pg_container.get_connection_url()
    # testcontainers returns postgresql+psycopg2:// or postgresql:// — normalize to postgresql://
    if "postgresql+psycopg2://" in url:
        url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    elif "postgresql+asyncpg://" in url:
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    connection = await asyncpg.connect(url)
    yield connection
    await connection.close()
