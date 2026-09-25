from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.sqlalchemy_url,  # postgresql+asyncpg://…
    pool_pre_ping=True,
    # TIMESTAMP(3) has no zone: pin the session to UTC so DB now() agrees with datetime.now(UTC).
    connect_args={"server_settings": {"timezone": "UTC"}},
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Request-scoped session. The service layer owns transaction boundaries; handlers never commit."""
    async with SessionLocal() as session:
        yield session


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """For work that outlives the request (background email dispatch)."""
    return SessionLocal
