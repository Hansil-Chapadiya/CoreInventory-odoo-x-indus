"""
Async SQLAlchemy database engine and session factory.
Configured for Neon PostgreSQL (SSL required).
"""

import ssl

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _build_connect_args() -> dict:
    """Build connection args with SSL for Neon DB."""
    if "neon.tech" in settings.DATABASE_URL:
        ssl_ctx = ssl.create_default_context()
        return {"ssl": ssl_ctx}
    return {}


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    connect_args=_build_connect_args(),
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
