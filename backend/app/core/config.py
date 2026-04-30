from pydantic_settings import BaseSettings
from functools import lru_cache
import os


def _fix_db_url(url: str) -> str:
    """
    Both Heroku (postgres://) and Supabase (postgresql://) need to be
    converted to postgresql+asyncpg:// for SQLAlchemy async engine.
    """
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


class Settings(BaseSettings):
    # App
    APP_NAME: str = "FarmaScan API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database — SQLite for dev, Supabase/Heroku Postgres for prod
    DATABASE_URL: str = "sqlite+aiosqlite:///./farmascan.db"

    # CORS — comma-separated list (Heroku doesn't parse JSON arrays in env vars)
    # NOTE: CORSMiddleware does NOT support wildcards in origins — use exact URLs.
    CORS_ORIGINS: str = "http://localhost:4200,http://localhost:80,https://farmascan.netlify.app"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # File processing
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 500
    BATCH_SIZE: int = 10_000  # rows per DB insert batch

    # Curva reference — single-sheet BUSCARV equivalent:
    # =SI.ERROR(BUSCARV(C2, $B$2:$G$12921, 6, 0), 0)
    CURVA_LOOKUP_KEY_COL: int = 1        # 0-indexed col B
    CURVA_RESULT_COL: int = 5            # 0-indexed col G (6th col of B:G)
    CURVA_REFERENCE_ROW_END: int = 12920 # Excel rows 2..12921 → Python 0..12919

    @property
    def db_url(self) -> str:
        return _fix_db_url(self.DATABASE_URL)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
