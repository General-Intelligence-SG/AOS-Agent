"""Database engine, sessions, and lightweight SQLite schema migration helpers."""
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

SQLITE_PREFIX = "sqlite+aiosqlite:///"


def _sqlite_db_path() -> Path | None:
    if settings.DATABASE_URL.startswith(SQLITE_PREFIX):
        return Path(settings.DATABASE_URL[len(SQLITE_PREFIX):])
    return None


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    return {row[1] for row in rows}


def _sqlite_schema_requires_rebuild(db_path: Path) -> bool:
    if not db_path.exists():
        return False

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if not tables:
            return False

        if "personas" in tables:
            required_persona_columns = {
                "tenant_id",
                "agent_id",
                "persona_type",
                "version_no",
            }
            if not required_persona_columns.issubset(_table_columns(conn, "personas")):
                return True

        if "objects" in tables:
            required_object_columns = {
                "tenant_id",
                "object_type",
                "title",
                "visibility",
                "current_version",
            }
            if not required_object_columns.issubset(_table_columns(conn, "objects")):
                return True

        if "chat_sessions" in tables and "conversations" not in tables:
            return True

    return False


def _backup_and_remove_sqlite(db_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(
        f"{db_path.stem}_pre_generalized_schema_{timestamp}{db_path.suffix}"
    )
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as source:
        with sqlite3.connect(backup_path) as target:
            source.backup(target)

    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{db_path}{suffix}")
        if candidate.exists():
            candidate.unlink()

    return backup_path


async def init_db():
    """Create all tables and rebuild incompatible local SQLite schemas when needed."""
    sqlite_path = _sqlite_db_path()
    if sqlite_path and _sqlite_schema_requires_rebuild(sqlite_path):
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path = _backup_and_remove_sqlite(sqlite_path)
        print(
            f"Detected incompatible SQLite schema. Backed up old database to "
            f"{backup_path} and rebuilding with the generalized schema."
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Yield a database session with automatic commit/rollback."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
