from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
)


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Lightweight, idempotent SQLite schema migrations
# ---------------------------------------------------------------------------

# Columns added in v0.2 that may be absent from databases created by v0.1.
_V2_POST_COLUMNS = [
    ("topic_url",          "TEXT"),
    ("source_name",        "TEXT"),
    ("source_published_at","DATETIME"),
    ("editorial_score",    "INTEGER"),
    ("score_breakdown",    "TEXT"),
    ("generation_provider","TEXT"),
    ("generation_model",   "TEXT"),
]

# Unique partial index on (agent_id, topic_url) WHERE topic_url IS NOT NULL.
# Safe for existing data because all v0.1 rows have NULL topic_url.
_V2_INDEXES = [
    (
        "CREATE UNIQUE INDEX IF NOT EXISTS uix_posts_agent_topic_url "
        "ON posts (agent_id, topic_url) WHERE topic_url IS NOT NULL"
    ),
]


def run_migrations(sync_conn) -> None:
    """
    Idempotently apply SQLite schema migrations.

    Designed to be called via ``AsyncConnection.run_sync(run_migrations)``
    during application startup, before ``Base.metadata.create_all``.

    Each ALTER TABLE statement is attempted individually so that an already-
    existing column does not abort the remaining migrations.
    """
    for col_name, col_type in _V2_POST_COLUMNS:
        try:
            sync_conn.execute(
                text(f"ALTER TABLE posts ADD COLUMN {col_name} {col_type}")
            )
        except Exception:
            # "table posts already has column X" – safe to ignore.
            pass

    for index_sql in _V2_INDEXES:
        try:
            sync_conn.execute(text(index_sql))
        except Exception:
            # Index already exists – safe to ignore.
            pass