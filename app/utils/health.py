"""Health check helpers for PostgreSQL and Redis."""

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine


def check_database() -> str:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


def check_redis() -> str:
    try:
        import redis

        client = redis.from_url(str(get_settings().redis_url))
        client.ping()
        return "ok"
    except Exception:
        return "error"
