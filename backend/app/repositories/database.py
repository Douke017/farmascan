from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import get_settings

settings = get_settings()

# Supabase uses PgBouncer in transaction pool mode, which is incompatible
# with asyncpg's prepared statements. Disabling them via statement_cache_size=0
# is required. This only applies to PostgreSQL — not SQLite (local dev).
_is_postgres = settings.db_url.startswith("postgresql")
_connect_args = {"statement_cache_size": 0} if _is_postgres else {}

engine = create_async_engine(
    settings.db_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields a DB session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables on startup."""
    async with engine.begin() as conn:
        from app.models import inventory  # noqa: F401 — ensures models are registered
        await conn.run_sync(Base.metadata.create_all)
